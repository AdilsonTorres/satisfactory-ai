"""
Activities package — re-exports all Temporal activity functions.

Split by where they can run:
  GAME_ACTIVITIES    — touch the screen / input devices / KWin; only the
                       host game worker (workers/worker.py) can run these.
  PERSIST_ACTIVITIES — pure persistence (stats JSON, SQLite gift history);
                       run on the persist queue inside the Dockerized
                       orchestrator worker (workers/orchestrator.py).
"""

from collections.abc import Callable, Sequence
from typing import Any

from activities.combat import check_ammo_count, engage_enemy, retreat_from_hazard, scan_for_enemy
from activities.control import send_workflow_signal
from activities.crafting import craft_rifle_ammo, harvest_resource_node
from activities.diagnostics import (
    capture_template_screen,
    extract_templates_from_screen,
    persist_session_stats,
    take_debug_screenshot,
    verify_matching_templates,
)
from activities.exploration import capture_base_reference, explore_leg, get_exploration_route, return_via_reverse_route
from activities.inventory import (
    check_inventory_full,
    collect_doggo_gift,
    feed_wild_doggo,
    open_storage_and_deposit_loot,
)
from activities.lifecycle import check_health_low, handle_death_respawn, reset_to_safe_state
from activities.navigation import navigate_back_to_base, navigate_to_equipment_workshop, navigate_to_location
from activities.records import record_gift_check

GAME_ACTIVITIES: Sequence[Callable[..., Any]] = [
    check_ammo_count,
    collect_doggo_gift,
    capture_base_reference,
    capture_template_screen,
    check_health_low,
    check_inventory_full,
    craft_rifle_ammo,
    engage_enemy,
    explore_leg,
    extract_templates_from_screen,
    feed_wild_doggo,
    get_exploration_route,
    handle_death_respawn,
    harvest_resource_node,
    navigate_back_to_base,
    navigate_to_equipment_workshop,
    navigate_to_location,
    open_storage_and_deposit_loot,
    reset_to_safe_state,
    retreat_from_hazard,
    return_via_reverse_route,
    scan_for_enemy,
    take_debug_screenshot,
    verify_matching_templates,
]

PERSIST_ACTIVITIES: Sequence[Callable[..., Any]] = [
    persist_session_stats,
    record_gift_check,
    send_workflow_signal,
]

ALL_ACTIVITIES: Sequence[Callable[..., Any]] = [*GAME_ACTIVITIES, *PERSIST_ACTIVITIES]
