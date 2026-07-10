import asyncio
from typing import Any

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows.combat_patrol import CombatPatrolWorkflow
from workflows.exploration import ExplorationWorkflow

# ==============================================================================
# 1. Mock Activities Definitions
# ==============================================================================


@activity.defn(name="get_exploration_route")
async def mock_get_exploration_route() -> dict:
    return {
        "route": [{"keys": ["w"], "duration": 2.0, "turn_dx": 0}, {"keys": ["w", "d"], "duration": 1.5, "turn_dx": 0}],
        "max_total_duration_seconds": 10.0,
        "check_interval": 1.0,
        "ascend_every": 2,
        "ascend_pulse": 0.3,
        "gauge_low_abort": 0.25,
    }


@activity.defn(name="capture_base_reference")
async def mock_capture_base_reference() -> None:
    pass


# A helper list to capture arguments passed to the mock explore_leg
explore_leg_calls: list[dict[str, Any]] = []


@activity.defn(name="explore_leg")
async def mock_explore_leg(
    keys: list[str],
    duration: float,
    turn_dx: int,
    leg_idx: int,
    check_interval: float,
    ascend_every: int,
    ascend_pulse: float,
    gauge_low_abort: float,
) -> dict:
    explore_leg_calls.append({"keys": keys, "duration": duration, "turn_dx": turn_dx, "leg_idx": leg_idx})

    # Simulate a gauge abort on leg index 1 if requested by test
    should_abort_gauge = leg_idx == 1 and duration == 1.5 and keys == ["w", "d"]

    return {
        "died": False,
        "health_low": False,
        "gauge_low": should_abort_gauge,
        "min_health_frac": 1.0,
        "duration": duration if not should_abort_gauge else 0.5,
    }


@activity.defn(name="return_via_reverse_route")
async def mock_return_via_reverse_route(legs_taken: list) -> None:
    pass


@activity.defn(name="handle_death_respawn")
async def mock_handle_death_respawn() -> None:
    pass


# Combat activities mock state
combat_enemy_queue: list[dict[str, Any]] = []
combat_engagement_results: list[str] = []
engage_enemy_calls: list[dict[str, Any]] = []


@activity.defn(name="scan_for_enemy")
async def mock_scan_for_enemy() -> dict[str, Any]:
    if combat_enemy_queue:
        return combat_enemy_queue.pop(0)
    return {"found": False, "x": 0, "y": 0, "confidence": 0.0, "type": "", "hazard": False}


@activity.defn(name="engage_enemy")
async def mock_engage_enemy(target_x: int, target_y: int, enemy_type: str = "") -> str:
    engage_enemy_calls.append({"x": target_x, "y": target_y, "type": enemy_type})
    if combat_engagement_results:
        return combat_engagement_results.pop(0)
    return "killed"


@activity.defn(name="retreat_from_hazard")
async def mock_retreat_from_hazard() -> bool:
    return True


# Persistence activities (run on PERSIST_TASK_QUEUE)
@activity.defn(name="persist_session_stats")
async def mock_persist_session_stats(workflow_type: str, stats: dict) -> None:
    pass


@activity.defn(name="take_debug_screenshot")
async def mock_take_debug_screenshot(label: str) -> None:
    pass


# =/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=
# 2. Synchronous Test Cases (Internal asyncio.run)
# =/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=/=


def test_exploration_workflow_success():
    global explore_leg_calls
    explore_leg_calls.clear()

    async def run_test():
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            # Start game activities worker and secondary persistence worker concurrently
            async with (
                Worker(
                    env.client,
                    task_queue="test-explore-queue",
                    workflows=[ExplorationWorkflow],
                    activities=[
                        mock_get_exploration_route,
                        mock_capture_base_reference,
                        mock_explore_leg,
                        mock_return_via_reverse_route,
                    ],
                ),
                Worker(
                    env.client,
                    task_queue="satisfactory-persist",
                    activities=[mock_persist_session_stats, mock_take_debug_screenshot],
                ),
            ):
                result = await env.client.execute_workflow(
                    ExplorationWorkflow.run,
                    args=[10.0, False, False],  # max_seconds, ignore_health, no_return
                    id="test-exploration-wf-success",
                    task_queue="test-explore-queue",
                )

                assert result["status"] == "completed"
                assert result["legs_completed"] == 2
                assert result["returned"] is True
                assert len(explore_leg_calls) == 2
                assert explore_leg_calls[0]["keys"] == ["w"]
                assert explore_leg_calls[1]["keys"] == ["w", "d"]
        finally:
            await env.shutdown()

    asyncio.run(run_test())


def test_exploration_workflow_no_return():
    global explore_leg_calls
    explore_leg_calls.clear()

    async def run_test():
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            async with (
                Worker(
                    env.client,
                    task_queue="test-explore-queue",
                    workflows=[ExplorationWorkflow],
                    activities=[
                        mock_get_exploration_route,
                        mock_capture_base_reference,
                        mock_explore_leg,
                        mock_return_via_reverse_route,
                    ],
                ),
                Worker(
                    env.client,
                    task_queue="satisfactory-persist",
                    activities=[mock_persist_session_stats, mock_take_debug_screenshot],
                ),
            ):
                result = await env.client.execute_workflow(
                    ExplorationWorkflow.run,
                    # max_seconds=10.0, ignore_health=False, no_return=True
                    args=[10.0, False, True],
                    id="test-exploration-wf-no-return",
                    task_queue="test-explore-queue",
                )

                assert result["status"] == "completed"
                assert result["legs_completed"] == 2
                assert result["returned"] is False  # stayed at target!
        finally:
            await env.shutdown()

    asyncio.run(run_test())


def test_exploration_workflow_gauge_abort():
    global explore_leg_calls
    explore_leg_calls.clear()

    async def run_test():
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            async with (
                Worker(
                    env.client,
                    task_queue="test-explore-queue",
                    workflows=[ExplorationWorkflow],
                    activities=[
                        mock_get_exploration_route,
                        mock_capture_base_reference,
                        mock_explore_leg,
                        mock_return_via_reverse_route,
                    ],
                ),
                Worker(
                    env.client,
                    task_queue="satisfactory-persist",
                    activities=[mock_persist_session_stats, mock_take_debug_screenshot],
                ),
            ):
                result = await env.client.execute_workflow(
                    ExplorationWorkflow.run,
                    args=[10.0, False, False],
                    id="test-exploration-wf-gauge-abort",
                    task_queue="test-explore-queue",
                )

                # In mock_explore_leg, we trigger a gauge abort on leg index 1.
                # The workflow should abort the outbound leg loop and trigger return_via_reverse_route.
                assert result["status"] == "completed"
                assert result["gauge_aborts"] == 1
                assert result["legs_completed"] == 2  # both leg 0 and leg 1 ran
                assert result["returned"] is True
        finally:
            await env.shutdown()

    asyncio.run(run_test())


def test_combat_patrol_workflow():
    global combat_enemy_queue, combat_engagement_results, engage_enemy_calls
    engage_enemy_calls.clear()

    # Setup mock sequence of scanned enemies
    combat_enemy_queue = [
        {"found": True, "x": 100, "y": 200, "confidence": 0.95, "type": "enemy_hog", "hazard": False},
        {"found": True, "x": 150, "y": 250, "confidence": 0.90, "type": "enemy_spitter", "hazard": False},
        {
            "found": True,
            "x": 300,
            "y": 400,
            "confidence": 0.99,
            "type": "enemy_hog_nuclear",
            "hazard": True,
        },  # Hazard (retreats)
        {
            "found": True,
            "x": 200,
            "y": 300,
            "confidence": 0.88,
            "type": "enemy_stinger",
            "hazard": False,
        },  # Player dies in this engagement
    ]

    # Setup mock engagement results
    # 1. Hog killed, 2. Spitter killed, 3. (Nuclear hog bypassed), 4. Player dies
    combat_engagement_results = ["killed", "killed", "died"]

    async def run_test():
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            async with (
                Worker(
                    env.client,
                    task_queue="test-combat-patrol-queue",
                    workflows=[CombatPatrolWorkflow],
                    activities=[
                        mock_scan_for_enemy,
                        mock_engage_enemy,
                        mock_retreat_from_hazard,
                        mock_handle_death_respawn,
                    ],
                ),
                Worker(
                    env.client,
                    task_queue="satisfactory-persist",
                    activities=[mock_persist_session_stats, mock_take_debug_screenshot],
                ),
            ):
                result = await env.client.execute_workflow(
                    CombatPatrolWorkflow.run,
                    args=[2, 5],  # max_kills=2, screenshot_every_kills=5
                    id="test-combat-patrol-wf",
                    task_queue="test-combat-patrol-queue",
                )

                assert result["status"] == "stopped"
                assert result["kills"] == 2
                assert len(engage_enemy_calls) == 2
                # Verify correct parameters were passed to engage_enemy (specifically target names for strategy selection)
                assert engage_enemy_calls[0]["type"] == "enemy_hog"
                assert engage_enemy_calls[1]["type"] == "enemy_spitter"
        finally:
            await env.shutdown()

    asyncio.run(run_test())
