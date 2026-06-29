"""
activities/combat.py

Combat-related activities.
"""

import logging
import time

from temporalio import activity

from utils import config as cfg
from utils import input as inp
from utils.screenshot import save_debug_screenshot

from ._shared import _check_health_inline, get_vision, screenshot_on_error

logger = logging.getLogger(__name__)

# Variants that deal area damage (radiation/gas) — engage_enemy's static
# aim-and-shoot loop wasn't designed for this. Workflows should treat
# "hazard" as a signal to retreat instead of engaging normally.
HAZARD_ENEMY_TYPES = {"enemy_hog_nuclear", "enemy_stinger_elite_gas"}


@activity.defn
async def scan_for_enemy() -> dict:
    v = get_vision()
    result = v.find_enemy()

    if result:
        hazard = result.template_name in HAZARD_ENEMY_TYPES
        logger.info(
            "Enemy '%s' at (%d,%d) conf=%.2f hazard=%s",
            result.template_name,
            result.x,
            result.y,
            result.confidence,
            hazard,
        )
        return {
            "found": True,
            "x": result.x,
            "y": result.y,
            "confidence": result.confidence,
            "type": result.template_name,
            "hazard": hazard,
        }

    return {"found": False, "x": 0, "y": 0, "confidence": 0.0, "type": "", "hazard": False}


@activity.defn
async def engage_enemy(
    target_x: int,
    target_y: int,
    screen_w: int | None = None,
    screen_h: int | None = None,
) -> str:
    """
    Engages an enemy at (target_x, target_y).
    Combat parameters come from config.toml[combat].
    Returns: 'killed' | 'escaped' | 'died'
    """
    with screenshot_on_error("engage_enemy"):
        v = get_vision()
        disp = cfg.get("display", {})
        sw = screen_w or disp.get("screen_width", 1920)
        sh = screen_h or disp.get("screen_height", 1080)
        center_x, center_y = sw // 2, sh // 2
        max_dur = cfg.get("combat.max_combat_duration_seconds", 10.0)

        logger.info("Engaging enemy at (%d,%d)", target_x, target_y)
        inp.aim_at_screen_position(target_x, target_y, center_x, center_y)
        time.sleep(0.1)

        combat_start = time.time()
        bursts_fired = 0

        while time.time() - combat_start < max_dur:
            activity.heartbeat(f"combat — {bursts_fired} bursts")

            # _check_health_inline avoids calling another activity from inside an activity
            if _check_health_inline(v):
                logger.warning("Low health — fleeing.")
                inp.dodge()
                inp.move_backward(1.0)
                return "escaped"

            inp.shoot()
            bursts_fired += 1
            time.sleep(0.1)

            enemy = v.find_enemy()
            if not enemy:
                logger.info("Enemy eliminated after %d bursts.", bursts_fired)
                break

            inp.aim_at_screen_position(enemy.x, enemy.y, center_x, center_y)

        if v._death_overlay_present():
            save_debug_screenshot("player_death")
            logger.error("Character died during combat.")
            return "died"

        time.sleep(0.8)
        try:
            remains = v.find("enemy_remains_prompt")
            if remains.found:
                inp.loot_remains()
                if v.wait_for("inventory_open", timeout=3.0).found:
                    time.sleep(0.4)
                    inp.close_menu()
                    logger.info("Loot collected.")
        except FileNotFoundError:
            logger.warning("Template 'enemy_remains_prompt' not found in templates/. Skipping remains looting.")

        return "killed"


@activity.defn
async def retreat_from_hazard() -> bool:
    """
    Retreats without engaging — used when scan_for_enemy signals 'hazard'
    (a radiation/gas area-damage variant). engage_enemy's static
    aim-and-shoot loop isn't safe against these variants.
    """
    inp.move_backward(1.5)
    inp.dodge()
    logger.warning("Retreating from a hazard enemy (area damage) without engaging.")
    return True


@activity.defn
async def check_ammo_count() -> int:
    """
    Reads the ammo count from the HUD via OCR (region configurable in
    config.toml [combat.ammo_region]). Returns -1 if the reading fails or
    the region isn't calibrated — the workflow treats -1 as "unknown" and
    doesn't block combat because of it.
    """
    v = get_vision()
    region = cfg.get("combat.ammo_region", {})
    text = v.read_text_region(
        region.get("x", 0),
        region.get("y", 0),
        region.get("w", 80),
        region.get("h", 40),
    )
    try:
        count = int(text)
        logger.debug("Ammo detected: %d", count)
        return count
    except ValueError:
        logger.warning("Failed to read ammo count (OCR returned '%s').", text)
        return -1
