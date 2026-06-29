"""
workflows/tame_doggo.py

Lizard Doggo taming workflow.
"""

import asyncio
from datetime import timedelta

from temporalio import workflow

from ._base import (
    GAME_RETRY,
    _cleanup_on_cancel,
    _ControlMixin,
    _save_stats,
    _screenshot,
)

with workflow.unsafe.imports_passed_through():
    from activities.inventory import feed_wild_doggo


@workflow.defn
class TameDoggoWorkflow(_ControlMixin):
    """
    Tries to tame a wild Lizard Doggo by repeatedly offering Paleberries
    (multiple doggos compete for the same berry, so repeating helps).

    Actual success — the Doggo ate, jumped, and "squeaked" — is not
    verified automatically (the visual cue is too weak for reliable
    template matching). Best-effort: review each attempt's screenshots
    manually in debug_screenshots/.

    Parameters:
        max_attempts (int):              Feeding attempts [5]
        seconds_between_attempts (int):  Wait between attempts [15]

    get_stats query returns:
        {attempts, fed, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {"attempts": 0, "fed": 0, "status": "running"}

    @workflow.run
    async def run(self, max_attempts: int = 5, seconds_between_attempts: int = 15) -> dict:
        workflow.logger.info("TameDoggoWorkflow started. max_attempts=%d", max_attempts)
        try:
            while self._stats["attempts"] < max_attempts and not self._stop_requested:
                await self._wait_if_paused()
                if self._stop_requested:
                    break

                self._stats["attempts"] += 1
                attempt = self._stats["attempts"]

                fed = await workflow.execute_activity(
                    feed_wild_doggo,
                    start_to_close_timeout=timedelta(seconds=10),
                    schedule_to_close_timeout=timedelta(seconds=30),
                    retry_policy=GAME_RETRY,
                )
                if fed:
                    self._stats["fed"] += 1
                    await _screenshot(f"tame_attempt_{attempt}")

                await workflow.sleep(timedelta(seconds=seconds_between_attempts))

            self._stats["status"] = "stopped"
            await _save_stats("TameDoggoWorkflow", self._stats)
            return self._stats
        except asyncio.CancelledError:
            workflow.logger.warning("TameDoggoWorkflow cancelled — cleaning up game state.")
            await asyncio.shield(_cleanup_on_cancel("TameDoggoWorkflow"))
            raise
