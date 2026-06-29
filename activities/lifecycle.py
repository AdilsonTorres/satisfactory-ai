"""
activities/lifecycle.py

Lifecycle management activities.
"""

import logging
import time

from temporalio import activity

from utils import input as inp
from utils.exceptions import RespawnError
from utils.screenshot import save_debug_screenshot

from ._shared import _check_health_inline, get_vision, screenshot_on_error

logger = logging.getLogger(__name__)


@activity.defn
async def check_health_low() -> bool:
    """Checks for low health. When called from a workflow, uses normal Temporal dispatch."""
    return _check_health_inline(get_vision())


@activity.defn
async def handle_death_respawn() -> bool:
    """
    Confirms 'Press RMB to Respawn'. This isn't a clickable UI button at a
    fixed position (no 'respawn_button' template exists) — it's a global
    right-click action, confirmed live on 2026-06-25 from an actual death.
    Retries once since the cursor drifting to the screen edge from earlier
    UI interactions can cause the first attempt to be silently ignored.
    """
    with screenshot_on_error("handle_death_respawn"):
        v = get_vision()
        inp.respawn_confirm()
        time.sleep(3.0)

        if v._death_overlay_present():
            logger.warning("Still on death screen after first respawn attempt — retrying.")
            inp.respawn_confirm()
            time.sleep(3.0)

        if v._death_overlay_present():
            save_debug_screenshot("respawn_failed")
            raise RespawnError("Death screen still showing after two respawn attempts.")

        logger.info("Respawned.")
        return True


@activity.defn
async def reset_to_safe_state() -> bool:
    """
    Defensive cleanup: closes any open menu (gift, inventory, workshop).
    Called when cancelling/ending a workflow so the game isn't left with
    an open menu between one session and the next.
    """
    inp.close_menu()
    time.sleep(0.2)
    inp.close_menu()
    logger.info("Safe state restored (menus closed).")
    return True
