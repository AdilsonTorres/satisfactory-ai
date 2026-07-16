"""
tests/test_depot_and_gift_workflows.py

Temporal integration tests for:
  - DepotCoalToStorageWorkflow
  - GiftFarmWorkflow
"""

import asyncio
from typing import Any

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows.depot_coal import DepotCoalToStorageWorkflow
from workflows.gift_farm import GiftFarmWorkflow

# ==============================================================================
# Shared mock activities (persist queue)
# ==============================================================================


@activity.defn(name="persist_session_stats")
async def mock_persist_session_stats(workflow_type: str, stats: dict) -> None:
    pass


@activity.defn(name="take_debug_screenshot")
async def mock_take_debug_screenshot(label: str) -> None:
    pass


@activity.defn(name="record_gift_check")
async def mock_record_gift_check(result: dict) -> None:
    pass


# ==============================================================================
# DepotCoalToStorageWorkflow mocks
# ==============================================================================

download_calls: list[int] = []
deposit_calls: list[None] = []


@activity.defn(name="download_coal_from_depot")
async def mock_download_coal_from_depot(stacks: int) -> None:
    download_calls.append(stacks)


@activity.defn(name="deposit_coal_to_storage")
async def mock_deposit_coal_to_storage() -> int:
    deposit_calls.append(None)
    return 5  # always deposits 5 stacks


@activity.defn(name="reset_to_safe_state")
async def mock_reset_to_safe_state() -> None:
    pass


# ==============================================================================
# GiftFarmWorkflow mocks
# ==============================================================================

gift_results: list[dict[str, Any]] = []
inventory_full_responses: list[bool] = []


@activity.defn(name="collect_doggo_gift")
async def mock_collect_doggo_gift(doggos: list[dict]) -> dict:
    if gift_results:
        return gift_results.pop(0)
    # Default: nothing collected
    return {"doggo": doggos[0]["name"] if doggos else "doggo", "collected": False}


@activity.defn(name="check_inventory_full")
async def mock_check_inventory_full() -> bool:
    if inventory_full_responses:
        return inventory_full_responses.pop(0)
    return False


craft_calls: list[int] = []


@activity.defn(name="navigate_to_equipment_workshop")
async def mock_navigate_to_equipment_workshop() -> None:
    pass


@activity.defn(name="craft_rifle_ammo")
async def mock_craft_rifle_ammo(count: int) -> None:
    craft_calls.append(count)


@activity.defn(name="navigate_back_to_base")
async def mock_navigate_back_to_base() -> None:
    pass


# ==============================================================================
# DepotCoalToStorageWorkflow tests
# ==============================================================================


def test_depot_coal_workflow_fixed_cycles():
    """Runs 3 cycles and verifies stacks_transferred is correctly accumulated."""
    global download_calls, deposit_calls
    download_calls.clear()
    deposit_calls.clear()

    async def run_test():
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            async with (
                Worker(
                    env.client,
                    task_queue="test-depot-queue",
                    workflows=[DepotCoalToStorageWorkflow],
                    activities=[
                        mock_download_coal_from_depot,
                        mock_deposit_coal_to_storage,
                        mock_reset_to_safe_state,
                    ],
                ),
                Worker(
                    env.client,
                    task_queue="satisfactory-persist",
                    activities=[mock_persist_session_stats, mock_take_debug_screenshot],
                ),
            ):
                result = await env.client.execute_workflow(
                    DepotCoalToStorageWorkflow.run,
                    args=[1.0, 3, 5],  # interval=1s, max_cycles=3, stacks=5
                    id="test-depot-coal-3-cycles",
                    task_queue="test-depot-queue",
                )

                assert result["status"] == "stopped"
                assert result["cycles"] == 3
                assert result["stacks_transferred"] == 15  # 3 cycles x 5 stacks each
                assert len(download_calls) == 3
                assert all(s == 5 for s in download_calls)
        finally:
            await env.shutdown()

    asyncio.run(run_test())


def test_depot_coal_workflow_deposited_undefined_bug_regression():
    """
    Regression test: if deposit_coal_to_storage raises, the workflow must
    NOT crash with a NameError on `deposited`. It should log the error and
    continue to the next cycle.
    """
    download_calls.clear()
    deposit_calls.clear()

    @activity.defn(name="deposit_coal_to_storage")
    async def mock_deposit_raises() -> int:
        raise RuntimeError("Storage chest not found")

    async def run_test():
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            async with (
                Worker(
                    env.client,
                    task_queue="test-depot-crash-queue",
                    workflows=[DepotCoalToStorageWorkflow],
                    activities=[
                        mock_download_coal_from_depot,
                        mock_deposit_raises,
                        mock_reset_to_safe_state,
                    ],
                ),
                Worker(
                    env.client,
                    task_queue="satisfactory-persist",
                    activities=[mock_persist_session_stats, mock_take_debug_screenshot],
                ),
            ):
                result = await env.client.execute_workflow(
                    DepotCoalToStorageWorkflow.run,
                    args=[1.0, 2, 5],  # max_cycles=2 so test ends
                    id="test-depot-coal-deposit-crash",
                    task_queue="test-depot-crash-queue",
                )
                # Workflow must complete, not crash
                assert result["status"] == "stopped"
                assert result["cycles"] == 2
                assert result["stacks_transferred"] == 0  # deposit failed both times
        finally:
            await env.shutdown()

    asyncio.run(run_test())


# ==============================================================================
# GiftFarmWorkflow tests
# ==============================================================================


def test_gift_farm_workflow_collects_gift_and_crafts():
    """
    One cycle with a gift collected + full inventory → craft should trigger.
    """
    global gift_results, inventory_full_responses, craft_calls
    craft_calls.clear()
    inventory_full_responses.clear()
    gift_results.clear()

    roster = [{"name": "rex", "turn_dx": 0}]
    # First cycle: rex has a gift; inventory is full → trigger craft
    gift_results.append({"doggo": "rex", "collected": True, "item": "nobelisk", "slot_diff": 1})
    inventory_full_responses.append(True)

    async def run_test():
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            async with (
                Worker(
                    env.client,
                    task_queue="test-gift-farm-queue",
                    workflows=[GiftFarmWorkflow],
                    activities=[
                        mock_collect_doggo_gift,
                        mock_check_inventory_full,
                        mock_navigate_to_equipment_workshop,
                        mock_craft_rifle_ammo,
                        mock_navigate_back_to_base,
                        mock_reset_to_safe_state,
                        mock_take_debug_screenshot,
                    ],
                ),
                Worker(
                    env.client,
                    task_queue="satisfactory-persist",
                    activities=[
                        mock_persist_session_stats,
                        mock_take_debug_screenshot,
                        mock_record_gift_check,
                    ],
                ),
            ):
                # Use a very short interval so the test finishes quickly;
                # send stop after first cycle completes
                handle = await env.client.start_workflow(
                    GiftFarmWorkflow.run,
                    args=[roster, 50, 0, 0.5],  # doggos, ammo, screenshot_every=0, interval=0.5s
                    id="test-gift-farm-craft",
                    task_queue="test-gift-farm-queue",
                )
                # Let one cycle complete, then stop
                await asyncio.sleep(0.1)
                await handle.signal(GiftFarmWorkflow.stop)
                result = await handle.result()

                assert result["gifts"] >= 1
                assert result["gifts_by_doggo"].get("rex", 0) >= 1
                assert result["ammo_crafted"] == 50  # one craft cycle fired
                assert result["status"] == "stopped"
        finally:
            await env.shutdown()

    asyncio.run(run_test())


def test_gift_farm_workflow_no_gift_skips_inventory_check():
    """
    When no gift is collected, check_inventory_full must NOT be called
    (it's expensive menu churn and that's the whole optimization point).
    """
    global gift_results, inventory_full_responses, craft_calls
    gift_results.clear()
    inventory_full_responses.clear()
    craft_calls.clear()

    inventory_check_count = 0

    @activity.defn(name="check_inventory_full")
    async def mock_inv_full_counting() -> bool:
        nonlocal inventory_check_count
        inventory_check_count += 1
        return False

    roster = [{"name": "buddy", "turn_dx": 0}]
    # No gift available
    gift_results.append({"doggo": "buddy", "collected": False, "item": None, "slot_diff": 0})

    async def run_test():
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            async with (
                Worker(
                    env.client,
                    task_queue="test-gift-farm-no-inv-queue",
                    workflows=[GiftFarmWorkflow],
                    activities=[
                        mock_collect_doggo_gift,
                        mock_inv_full_counting,
                        mock_navigate_to_equipment_workshop,
                        mock_craft_rifle_ammo,
                        mock_navigate_back_to_base,
                        mock_reset_to_safe_state,
                        mock_take_debug_screenshot,
                    ],
                ),
                Worker(
                    env.client,
                    task_queue="satisfactory-persist",
                    activities=[
                        mock_persist_session_stats,
                        mock_take_debug_screenshot,
                        mock_record_gift_check,
                    ],
                ),
            ):
                handle = await env.client.start_workflow(
                    GiftFarmWorkflow.run,
                    args=[roster, 50, 0, 0.5],
                    id="test-gift-farm-no-inv-check",
                    task_queue="test-gift-farm-no-inv-queue",
                )
                await asyncio.sleep(0.1)
                await handle.signal(GiftFarmWorkflow.stop)
                result = await handle.result()

                assert result["gifts"] == 0
                assert inventory_check_count == 0, (
                    "check_inventory_full should NOT be called when no gift was collected"
                )
        finally:
            await env.shutdown()

    asyncio.run(run_test())
