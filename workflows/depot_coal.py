from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import our activities
with workflow.unsafe.imports_passed_through():
    from activities import deposit_coal_to_storage, download_coal_from_depot

GAME_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_attempts=5,
)


@workflow.defn
class DepotCoalToStorageWorkflow:
    def __init__(self) -> None:
        self._stats = {"cycles": 0, "stacks_transferred": 0}
        self._stop_requested = False

    @workflow.run
    async def run(
        self,
        interval_seconds: float = 15.0,
        max_cycles: int | None = None,
        stacks_per_cycle: int = 5,
    ) -> dict:
        workflow.logger.info("DepotCoalToStorageWorkflow started.")

        while not self._stop_requested:
            if max_cycles is not None and self._stats["cycles"] >= max_cycles:
                break

            self._stats["cycles"] += 1
            cycle = self._stats["cycles"]
            workflow.logger.info("Cycle #%d starting.", cycle)

            # Step 1: Download Coal from depot
            try:
                await workflow.execute_activity(
                    download_coal_from_depot,
                    args=[stacks_per_cycle],
                    schedule_to_close_timeout=timedelta(seconds=60),
                    retry_policy=GAME_RETRY,
                )
            except Exception as exc:
                workflow.logger.error("download_coal_from_depot failed: %s", exc)
                # Wait before retrying next cycle
                await workflow.sleep(timedelta(seconds=interval_seconds))
                continue

            # Step 2: Deposit Coal to storage
            try:
                deposited = await workflow.execute_activity(
                    deposit_coal_to_storage,
                    schedule_to_close_timeout=timedelta(seconds=60),
                    retry_policy=GAME_RETRY,
                )
                self._stats["stacks_transferred"] += deposited
            except Exception as exc:
                workflow.logger.error("deposit_coal_to_storage failed: %s", exc)

            workflow.logger.info(
                "Cycle #%d finished. Deposited stacks: %d (total: %d)",
                cycle,
                deposited,
                self._stats["stacks_transferred"],
            )

            # Sleep until next cycle
            await workflow.sleep(timedelta(seconds=interval_seconds))

        return self._stats

    @workflow.signal
    def stop(self) -> None:
        self._stop_requested = True

    @workflow.query
    def get_stats(self) -> dict:
        return self._stats
