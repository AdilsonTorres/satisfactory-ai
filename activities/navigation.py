"""
activities/navigation.py

Navigation activities.
"""

import logging

from temporalio import activity

from utils import config as cfg
from utils import input as inp
from utils.exceptions import NavigationError

from ._shared import get_vision, screenshot_on_error

logger = logging.getLogger(__name__)


@activity.defn
async def navigate_to_location(location: str) -> bool:
    """
    Navigates to a named location in config.toml [locations.<location>]:
    runs the fixed key/duration sequence (steps) and, if the location has
    an 'arrival_template', confirms arrival via vision.

    Generalizes the pattern used by navigate_to_equipment_workshop to
    arbitrary locations (combat zones, storage, etc.) without needing a
    dedicated activity for each one.
    """
    with screenshot_on_error(f"navigate_to_{location}"):
        loc = cfg.get(f"locations.{location}")
        if not loc:
            raise NavigationError(f"Location '{location}' not defined in config.toml [locations.{location}].")

        steps = loc.get("steps", [])
        logger.info("Navigating to '%s' (%d step(s))...", location, len(steps))
        for i, step in enumerate(steps):
            activity.heartbeat(f"step {i + 1}/{len(steps)} of '{location}'")
            inp.hold(step["key"], step.get("duration", 0.5))

        arrival_template = loc.get("arrival_template")
        if arrival_template:
            v = get_vision()
            result = v.wait_for(arrival_template, timeout=loc.get("arrival_timeout", 5.0))
            if not result.found:
                raise NavigationError(
                    f"Arrival at '{location}' not confirmed — template "
                    f"'{arrival_template}' not found. Adjust [locations.{location}] in config.toml."
                )

        logger.info("Arrival at '%s' complete.", location)
        return True


@activity.defn
async def navigate_to_equipment_workshop() -> bool:
    """
    Navigates to the Equipment Workshop via the key sequence configured in
    config.toml. If it fails, adjust [navigation] in config.toml.
    """
    with screenshot_on_error("navigate_to_workshop"):
        nav = cfg.get("navigation", {})
        logger.info("Navigating to the Equipment Workshop...")
        activity.heartbeat("starting navigation")

        inp.move_forward(nav.get("to_workshop_forward_1", 1.2))
        activity.heartbeat("walking forward (1)")
        inp.strafe_right(nav.get("to_workshop_strafe_right", 0.8))
        inp.move_forward(nav.get("to_workshop_forward_2", 0.5))

        v = get_vision()
        result = v.wait_for("equipment_workshop_prompt", timeout=5.0)
        if not result.found:
            raise NavigationError("Equipment Workshop not found after navigation. Adjust [navigation] in config.toml.")

        logger.info("Workshop at (%d,%d).", result.x, result.y)
        return True


@activity.defn
async def navigate_back_to_base() -> bool:
    """
    Returns to the farming spot. Verifies the character actually left the
    Workshop area (if the prompt is still visible, the movement had no
    effect — collision, obstruction, etc).
    """
    with screenshot_on_error("navigate_back_to_base"):
        nav = cfg.get("navigation", {})
        inp.move_backward(nav.get("back_to_base_backward_1", 1.2))
        inp.strafe_left(nav.get("back_to_base_strafe_left", 0.8))
        inp.move_backward(nav.get("back_to_base_backward_2", 0.5))

        v = get_vision()
        if v.find("equipment_workshop_prompt").found:
            raise NavigationError(
                "Still inside the Equipment Workshop area after navigating back. "
                "The character may be obstructed. Adjust [navigation] in config.toml."
            )
        return True
