"""
workflows/exploration.py

Exploration workflow doing blind route runs and health/death monitoring.
"""

import asyncio
import math
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

from ._base import (
    NAV_RETRY,
    NO_RETRY,
    _cleanup_on_cancel,
    _ControlMixin,
    _save_stats,
)

with workflow.unsafe.imports_passed_through():
    from pydantic import BaseModel

    from activities.exploration import (
        capture_base_reference,
        explore_leg,
        get_exploration_route,
        return_via_reverse_route,
    )
    from activities.lifecycle import handle_death_respawn


class ExplorationParams(BaseModel):
    max_total_duration_seconds: float | None = None
    ignore_health_check: bool = False
    no_return: bool = False


@workflow.defn
class ExplorationWorkflow(_ControlMixin):
    """
    Unsupervised exploration around the base: captures a reference
    screenshot, then walks a configured route (config.toml
    [[exploration.route]]) leg by leg, optionally holding jump for
    Hover Pack ascend/glide, screenshotting and checking health/death
    after every leg. Stops early on low health, death, a 'stop' signal,
    or once max_total_duration_seconds of movement has been spent, then
    automatically retraces the legs taken (mirrored keys/turns) to head
    back toward the start.

    Parameters:
        max_total_duration_seconds (float, optional): overrides config.toml
        ignore_health_check (bool): skip the low-health abort [False].
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {
            "legs_completed": 0,
            "health_aborts": 0,
            "gauge_aborts": 0,
            "died": 0,
            "returned": False,
            "min_health_frac": 1.0,
            "status": "running",
        }

    @workflow.run
    async def run(
        self,
        max_total_duration_seconds: float | None = None,
        ignore_health_check: bool = False,
        no_return: bool = False,
    ) -> dict[str, Any]:
        params = ExplorationParams(
            max_total_duration_seconds=max_total_duration_seconds,
            ignore_health_check=ignore_health_check,
            no_return=no_return,
        )
        workflow.logger.info("ExplorationWorkflow started.")
        try:
            return await self._run_exploration(
                params.max_total_duration_seconds,
                params.ignore_health_check,
                params.no_return,
            )
        except asyncio.CancelledError:
            workflow.logger.warning("ExplorationWorkflow cancelled — cleaning up game state.")
            await asyncio.shield(_cleanup_on_cancel("ExplorationWorkflow"))
            raise

    async def _run_exploration(
        self,
        max_total_duration_seconds: float | None,
        ignore_health_check: bool = False,
        no_return: bool = False,
    ) -> dict[str, Any]:
        route_cfg = await workflow.execute_activity(
            get_exploration_route,
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        route = route_cfg["route"]
        max_duration = (
            max_total_duration_seconds
            if max_total_duration_seconds is not None
            else route_cfg["max_total_duration_seconds"]
        )
        check_interval = route_cfg["check_interval"]
        ascend_every = route_cfg["ascend_every"]
        ascend_pulse = route_cfg["ascend_pulse"]
        gauge_low_abort = route_cfg.get("gauge_low_abort", 0.25)

        await workflow.execute_activity(
            capture_base_reference,
            start_to_close_timeout=timedelta(seconds=25),
            schedule_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        legs_taken: list[dict[str, Any]] = []
        elapsed = 0.0
        died_mid_route = False

        for i, leg in enumerate(route):
            if self._stop_requested:
                break
            await self._wait_if_paused()
            if self._stop_requested:
                break

            duration = leg.get("duration", 1.0)
            if elapsed + duration > max_duration:
                workflow.logger.info(
                    "Reached max_total_duration_seconds (%.1fs) — stopping the outbound route.",
                    max_duration,
                )
                break

            num_chunks = max(1, math.ceil(duration / check_interval)) if check_interval > 0 else 1
            chunk_budget = num_chunks * 15 + 20
            try:
                result = await workflow.execute_activity(
                    explore_leg,
                    args=[
                        leg.get("keys", ["w"]),
                        duration,
                        leg.get("turn_dx", 0),
                        i,
                        check_interval,
                        ascend_every,
                        ascend_pulse,
                        gauge_low_abort,
                    ],
                    start_to_close_timeout=timedelta(seconds=chunk_budget),
                    schedule_to_close_timeout=timedelta(seconds=chunk_budget + 20),
                    heartbeat_timeout=timedelta(seconds=20),
                    retry_policy=NO_RETRY,
                )
            except Exception as exc:
                workflow.logger.error(
                    "Leg %d failed (%s) — stopping the outbound route and retracing what was already taken.",
                    i,
                    exc,
                )
                break

            legs_taken.append(result)
            elapsed += duration
            self._stats["legs_completed"] += 1
            self._stats["min_health_frac"] = min(self._stats["min_health_frac"], result.get("min_health_frac", 1.0))

            if result["died"]:
                died_mid_route = True
                self._stats["died"] += 1
                workflow.logger.warning("Death detected mid-exploration — respawning instead of retracing.")
                break

            if result["health_low"] and not ignore_health_check:
                self._stats["health_aborts"] += 1
                workflow.logger.warning("Low health mid-exploration — aborting outbound route early.")
                break

            if result.get("gauge_low", False):
                self._stats["gauge_aborts"] += 1
                workflow.logger.warning(
                    "Low Hover Pack gauge mid-exploration — aborting outbound route early to prevent falling."
                )
                break

        if died_mid_route:
            await workflow.execute_activity(
                handle_death_respawn,
                schedule_to_close_timeout=timedelta(seconds=45),
                retry_policy=NAV_RETRY,
            )
            self._stats["status"] = "died"
            await _save_stats("ExplorationWorkflow", self._stats)
            return self._stats

        if legs_taken and not no_return:
            return_budget = sum(leg["duration"] for leg in legs_taken)
            try:
                await workflow.execute_activity(
                    return_via_reverse_route,
                    args=[legs_taken],
                    start_to_close_timeout=timedelta(seconds=return_budget + 40),
                    schedule_to_close_timeout=timedelta(seconds=return_budget + 70),
                    heartbeat_timeout=timedelta(seconds=15),
                    retry_policy=NO_RETRY,
                )
                self._stats["returned"] = True
            except Exception as exc:
                workflow.logger.error("Return trip failed (%s) — character may not be back at the start.", exc)
        elif no_return:
            workflow.logger.info("no_return is True — staying at the destination.")

        self._stats["status"] = "completed"
        await _save_stats("ExplorationWorkflow", self._stats)
        return self._stats
