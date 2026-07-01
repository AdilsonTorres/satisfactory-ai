"""
activities/crafting.py

Crafting and harvesting activities.
"""

import logging
import time

from temporalio import activity

from utils import config as cfg
from utils import input as inp
from utils.exceptions import MenuError, VisionError

from ._shared import get_vision, press_until_closed, screenshot_on_error

logger = logging.getLogger(__name__)


@activity.defn
async def craft_rifle_ammo(quantity: int = 50) -> int:
    with screenshot_on_error("craft_rifle_ammo"):
        v = get_vision()

        inp.interact()
        activity.heartbeat("waiting for workshop menu")
        if not v.wait_for("workshop_menu_open", timeout=4.0).found:
            raise MenuError("Workshop menu did not open")

        ammo_icon = v.find("rifle_ammo_icon")
        if not ammo_icon.found:
            press_until_closed(v, "workshop_menu_open")
            r = ammo_icon
            raise VisionError("rifle_ammo_icon", r.confidence, cfg.get("vision.thresholds.rifle_ammo_icon", 0.85))

        inp.click(ammo_icon.x, ammo_icon.y)
        time.sleep(0.2)

        craft_btn = v.find("craft_button")
        if not craft_btn.found:
            press_until_closed(v, "workshop_menu_open")
            raise VisionError("craft_button", craft_btn.confidence, cfg.get("vision.thresholds.craft_button", 0.87))

        activity.heartbeat(f"crafting {quantity} unit(s)")
        from pynput.mouse import Button as _Btn
        from pynput.mouse import Controller as _MC

        _m = _MC()
        _m.position = (craft_btn.x, craft_btn.y)
        _m.press(_Btn.left)
        time.sleep(0.05 * quantity)
        _m.release(_Btn.left)

        time.sleep(0.5)
        press_until_closed(v, "workshop_menu_open")

        logger.info("Crafted ~%d Rifle Ammo.", quantity)
        return quantity


@activity.defn
async def harvest_resource_node(swings: int = 20) -> int:
    """
    Harvests a resource node (manual pickaxe or a node already opened up by
    a Nobelisk) by repeatedly pressing interact. Assumes the player is
    already positioned within range — there's no navigation to the node;
    that positioning is done manually once, like at the Workshop.
    """
    with screenshot_on_error("harvest_resource_node"):
        v = get_vision()
        check = v.find("resource_node_prompt")
        if not check.found:
            raise VisionError(
                "resource_node_prompt", check.confidence, cfg.get("vision.thresholds.resource_node_prompt", 0.80)
            )

        interval = cfg.get("harvesting.swing_interval_seconds", 0.5)
        count = 0
        for i in range(swings):
            activity.heartbeat(f"harvesting {i + 1}/{swings}")
            inp.interact()
            time.sleep(interval)
            count += 1

        logger.info("Harvest complete: %d interaction(s) on the node.", count)
        return count
