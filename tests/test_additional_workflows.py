from typing import Any

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows.combat_expedition import CombatExpeditionWorkflow
from workflows.control import SignalWorkflowAction
from workflows.depot_coal import DepotCoalToStorageWorkflow
from workflows.resource_harvest import ResourceHarvestWorkflow
from workflows.tame_doggo import TameDoggoWorkflow
from workflows.template_orchestration import TemplateOrchestrationWorkflow

# ==============================================================================
# Global call trackers for verification
# ==============================================================================
signal_calls: list[tuple[str, str]] = []
download_calls: list[int] = []
deposit_calls: list[int] = []
harvest_calls: list[int] = []
feed_calls: list[int] = []
capture_template_calls: list[tuple[str, str, str]] = []
extract_calls: list[str] = []
verify_calls: list[str] = []
check_ammo_calls: list[int] = []
engage_calls: list[str] = []
navigate_calls: list[str] = []
deposit_loot_calls: list[int] = []
enemy_queue: list[dict[str, Any]] = []


# ==============================================================================
# Mock Activities Definitions
# ==============================================================================
@activity.defn(name="send_workflow_signal")
async def mock_send_workflow_signal(target_workflow_id: str, signal_name: str) -> None:
    signal_calls.append((target_workflow_id, signal_name))


@activity.defn(name="download_coal_from_depot")
async def mock_download_coal_from_depot(stacks: int) -> int:
    download_calls.append(stacks)
    return stacks


@activity.defn(name="deposit_coal_to_storage")
async def mock_deposit_coal_to_storage() -> int:
    deposit_calls.append(3)
    return 3


@activity.defn(name="harvest_resource_node")
async def mock_harvest_resource_node(swings: int) -> int:
    harvest_calls.append(swings)
    return swings


@activity.defn(name="feed_wild_doggo")
async def mock_feed_wild_doggo() -> bool:
    feed_calls.append(1)
    return True


@activity.defn(name="capture_template_screen")
async def mock_capture_template_screen(name: str, open_key: str, close_key: str) -> str:
    capture_template_calls.append((name, open_key, close_key))
    return "test_captured_screen.png"


@activity.defn(name="extract_templates_from_screen")
async def mock_extract_templates_from_screen(
    screenshot_path: str, target: str = "hud", resolution: str = "2560x1440"
) -> dict:
    extract_calls.append(screenshot_path)
    return {"test_extracted_template.png": "dummy_content"}


@activity.defn(name="verify_matching_templates")
async def mock_verify_matching_templates(template_names: list[str]) -> dict:
    verify_calls.append(",".join(template_names))
    return {"verified": True}


@activity.defn(name="check_ammo_count")
async def mock_check_ammo_count() -> int:
    check_ammo_calls.append(1)
    return 50  # Enough ammo, so no resupply needed


@activity.defn(name="scan_for_enemy")
async def mock_scan_for_enemy() -> dict:
    if not enemy_queue:
        return {"found": False}
    return enemy_queue.pop(0)


@activity.defn(name="engage_enemy")
async def mock_engage_enemy(target_x: int, target_y: int, enemy_type: str = "") -> str:
    engage_calls.append(enemy_type)
    return "killed"


@activity.defn(name="retreat_from_hazard")
async def mock_retreat_from_hazard() -> None:
    pass


@activity.defn(name="handle_death_respawn")
async def mock_handle_death_respawn() -> None:
    pass


@activity.defn(name="navigate_to_location")
async def mock_navigate_to_location(location: str) -> None:
    navigate_calls.append(location)


@activity.defn(name="open_storage_and_deposit_loot")
async def mock_open_storage_and_deposit_loot() -> int:
    deposit_loot_calls.append(1)
    return 10


# Persist / debug activities needed by base workflows
@activity.defn(name="persist_session_stats")
async def mock_persist_session_stats(workflow_type: str, stats: dict) -> None:
    pass


@activity.defn(name="take_debug_screenshot")
async def mock_take_debug_screenshot(name: str) -> str:
    return "dummy_screenshot.png"


# ==============================================================================
# Tests Cases
# ==============================================================================
@pytest.mark.asyncio
async def test_signal_workflow_action():
    signal_calls.clear()
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        async with Worker(
            env.client,
            task_queue="satisfactory-persist",
            workflows=[SignalWorkflowAction],
            activities=[mock_send_workflow_signal],
        ):
            await env.client.execute_workflow(
                SignalWorkflowAction.run,
                args=["target-wf-123", "stop"],
                id="test-signal-wf",
                task_queue="satisfactory-persist",
            )
            assert len(signal_calls) == 1
            assert signal_calls[0] == ("target-wf-123", "stop")
    finally:
        await env.shutdown()


@pytest.mark.asyncio
async def test_depot_coal_workflow():
    download_calls.clear()
    deposit_calls.clear()
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        async with (
            Worker(
                env.client,
                task_queue="test-depot-coal-queue",
                workflows=[DepotCoalToStorageWorkflow],
                activities=[
                    mock_download_coal_from_depot,
                    mock_deposit_coal_to_storage,
                ],
            ),
            Worker(
                env.client,
                task_queue="satisfactory-persist",
                activities=[mock_persist_session_stats],
            ),
        ):
            result = await env.client.execute_workflow(
                DepotCoalToStorageWorkflow.run,
                args=[0.05, 2, 3],  # interval=0.05s, max_cycles=2, stacks=3
                id="test-depot-coal-wf",
                task_queue="test-depot-coal-queue",
            )
            assert result["cycles"] == 2
            assert result["stacks_transferred"] == 6
            assert len(download_calls) == 2
            assert download_calls == [3, 3]
            assert len(deposit_calls) == 2
    finally:
        await env.shutdown()


@pytest.mark.asyncio
async def test_resource_harvest_workflow():
    harvest_calls.clear()
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        async with (
            Worker(
                env.client,
                task_queue="test-harvest-queue",
                workflows=[ResourceHarvestWorkflow],
                activities=[mock_harvest_resource_node],
            ),
            Worker(
                env.client,
                task_queue="satisfactory-persist",
                activities=[mock_persist_session_stats, mock_take_debug_screenshot],
            ),
        ):
            result = await env.client.execute_workflow(
                ResourceHarvestWorkflow.run,
                args=[15, 3, 10],  # swings=15, cycles=3, screenshot=10
                id="test-harvest-wf",
                task_queue="test-harvest-queue",
            )
            assert result["cycles"] == 3
            assert result["total_swings"] == 45
            assert len(harvest_calls) == 3
            assert harvest_calls == [15, 15, 15]
    finally:
        await env.shutdown()


@pytest.mark.asyncio
async def test_tame_doggo_workflow():
    feed_calls.clear()
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        async with (
            Worker(
                env.client,
                task_queue="test-tame-doggo-queue",
                workflows=[TameDoggoWorkflow],
                activities=[mock_feed_wild_doggo, mock_take_debug_screenshot],
            ),
            Worker(
                env.client,
                task_queue="satisfactory-persist",
                activities=[mock_persist_session_stats, mock_take_debug_screenshot],
            ),
        ):
            result = await env.client.execute_workflow(
                TameDoggoWorkflow.run,
                args=[3, 1],  # max_attempts=3, seconds_between_attempts=1
                id="test-tame-doggo-wf",
                task_queue="test-tame-doggo-queue",
            )
            assert result["attempts"] == 3
            assert len(feed_calls) == 3
    finally:
        await env.shutdown()


@pytest.mark.asyncio
async def test_template_orchestration_workflow():
    capture_template_calls.clear()
    extract_calls.clear()
    verify_calls.clear()
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        async with Worker(
            env.client,
            task_queue="test-template-queue",
            workflows=[TemplateOrchestrationWorkflow],
            activities=[
                mock_capture_template_screen,
                mock_extract_templates_from_screen,
                mock_verify_matching_templates,
            ],
        ):
            result = await env.client.execute_workflow(
                TemplateOrchestrationWorkflow.run,
                args=["hud", "2560x1440"],
                id="test-template-wf",
                task_queue="test-template-queue",
            )
            assert result["screenshot"] == "test_captured_screen.png"
            assert result["extracted_templates"] == {"test_extracted_template.png": "dummy_content"}
            assert result["verification_results"] == {"verified": True}
            assert len(capture_template_calls) == 1
            assert capture_template_calls[0] == ("hud_base", "", "")
            assert len(extract_calls) == 1
            assert len(verify_calls) == 1
    finally:
        await env.shutdown()


@pytest.mark.asyncio
async def test_combat_expedition_workflow():
    global enemy_queue
    enemy_queue = [
        {"found": True, "x": 100, "y": 200, "confidence": 0.95, "type": "enemy_hog", "hazard": False},
        {"found": True, "x": 150, "y": 250, "confidence": 0.90, "type": "enemy_spitter", "hazard": False},
    ]
    check_ammo_calls.clear()
    navigate_calls.clear()
    deposit_loot_calls.clear()
    engage_calls.clear()

    env = await WorkflowEnvironment.start_time_skipping()
    try:
        async with (
            Worker(
                env.client,
                task_queue="test-combat-expedition-queue",
                workflows=[CombatExpeditionWorkflow],
                activities=[
                    mock_check_ammo_count,
                    mock_scan_for_enemy,
                    mock_engage_enemy,
                    mock_retreat_from_hazard,
                    mock_handle_death_respawn,
                    mock_navigate_to_location,
                    mock_open_storage_and_deposit_loot,
                    mock_take_debug_screenshot,
                ],
            ),
            Worker(
                env.client,
                task_queue="satisfactory-persist",
                activities=[mock_persist_session_stats, mock_take_debug_screenshot],
            ),
        ):
            result = await env.client.execute_workflow(
                CombatExpeditionWorkflow.run,
                args=["spitter_nest", 2, 20, 50, 5, "base", 30],
                id="test-combat-expedition-wf",
                task_queue="test-combat-expedition-queue",
            )
            assert result["status"] == "completed"
            assert result["kills"] == 2
            assert len(engage_calls) == 2
            assert engage_calls == ["enemy_hog", "enemy_spitter"]
            assert len(navigate_calls) == 2
            assert navigate_calls == ["spitter_nest", "base"]
            assert len(deposit_loot_calls) == 1
    finally:
        await env.shutdown()
