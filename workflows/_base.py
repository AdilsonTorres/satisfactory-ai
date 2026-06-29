"""
workflows/_base.py

Shared workflow infrastructure, mixins, and common helpers.
"""

import logging
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities.crafting import craft_rifle_ammo
    from activities.diagnostics import (
        persist_session_stats,
        take_debug_screenshot,
    )
    from activities.lifecycle import reset_to_safe_state
    from activities.navigation import navigate_back_to_base, navigate_to_equipment_workshop

logger = logging.getLogger(__name__)

GAME_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_attempts=3,
    backoff_coefficient=2.0,
    non_retryable_error_types=["FileNotFoundError"],
)

NAV_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    maximum_attempts=5,
    backoff_coefficient=1.5,
)

NO_RETRY = RetryPolicy(maximum_attempts=1)

_SS_TIMEOUT = timedelta(seconds=10)
_SS_RETRY = RetryPolicy(maximum_attempts=1)


async def _screenshot(label: str) -> None:
    await workflow.execute_activity(
        take_debug_screenshot,
        args=[label],
        schedule_to_close_timeout=_SS_TIMEOUT,
        retry_policy=_SS_RETRY,
    )


async def _save_stats(workflow_type: str, stats: dict) -> None:
    await workflow.execute_activity(
        persist_session_stats,
        args=[workflow_type, stats],
        schedule_to_close_timeout=timedelta(seconds=15),
        retry_policy=RetryPolicy(maximum_attempts=2),
    )


async def _cleanup_on_cancel(workflow_type: str) -> None:
    """Closes any open menus in the game before letting the cancellation exception propagate."""
    try:
        await workflow.execute_activity(
            reset_to_safe_state,
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
    except Exception as exc:
        workflow.logger.error("Cancellation cleanup for %s failed: %s", workflow_type, exc)


async def _run_craft_cycle(ammo_per_craft: int) -> None:
    await workflow.execute_activity(
        navigate_to_equipment_workshop,
        start_to_close_timeout=timedelta(seconds=10),
        schedule_to_close_timeout=timedelta(seconds=70),
        heartbeat_timeout=timedelta(seconds=8),
        retry_policy=NAV_RETRY,
    )
    await workflow.execute_activity(
        craft_rifle_ammo,
        args=[ammo_per_craft],
        start_to_close_timeout=timedelta(seconds=15),
        schedule_to_close_timeout=timedelta(seconds=60),
        heartbeat_timeout=timedelta(seconds=8),
        retry_policy=GAME_RETRY,
    )
    await workflow.execute_activity(
        navigate_back_to_base,
        start_to_close_timeout=timedelta(seconds=8),
        schedule_to_close_timeout=timedelta(seconds=60),
        retry_policy=NAV_RETRY,
    )


class _ControlMixin:
    """Signals and query shared by all workflows."""

    def __init__(self) -> None:
        self._paused = False
        self._stop_requested = False
        self._stats: dict = {"status": "running"}

    @workflow.signal
    async def pause(self) -> None:
        self._paused = True
        self._stats["status"] = "paused"
        workflow.logger.info("Paused.")

    @workflow.signal
    async def resume(self) -> None:
        self._paused = False
        self._stats["status"] = "running"
        workflow.logger.info("Resumed.")

    @workflow.signal
    async def stop(self) -> None:
        self._stop_requested = True
        self._paused = False
        self._stats["status"] = "stopping"
        workflow.logger.info("Shutdown requested.")

    @workflow.query
    def get_stats(self) -> dict:
        return self._stats

    async def _wait_if_paused(self) -> None:
        while self._paused and not self._stop_requested:
            await workflow.sleep(timedelta(seconds=1))
