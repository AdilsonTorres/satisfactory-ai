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

from ._shared import (
    _check_health_inline,
    close_open_menus,
    get_vision,
    screenshot_on_error,
)

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
    Defensive cleanup: drive the game back to plain gameplay (no menu),
    called when cancelling/ending a workflow so it isn't left with an open
    menu between sessions.

    Pressing Escape blindly TWICE is the classic desync bug: from gameplay the
    first Escape opens the pause menu and the second closes it (fine), but if a
    game menu (inventory/workshop/gift) was open, the first Escape closes it and
    the second OPENS the pause menu — leaving a menu up. So we drive by
    observation instead: detect which menu (if any) is actually open and close
    exactly that one with a verified press, never pressing Escape blindly.
    """
    v = get_vision()
    inp.focus_game()
    open_now = close_open_menus(v)
    if not open_now:
        logger.info("Safe state: no menu detected, already in gameplay.")
    else:
        logger.info("Safe state: closed %s.", ", ".join(open_now))
    return True
