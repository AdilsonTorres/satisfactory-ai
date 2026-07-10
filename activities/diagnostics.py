"""
activities/diagnostics.py

Debug and diagnostic activities.
"""

import logging

from temporalio import activity

from utils import input as inp
from utils import stats as stats_module
from utils.screenshot import save_debug_screenshot

from ._shared import get_vision

logger = logging.getLogger(__name__)


@activity.defn
def take_debug_screenshot(label: str = "manual") -> str:
    """Takes an immediate screenshot. Can be called from any workflow."""
    path = save_debug_screenshot(label)
    logger.info("Screenshot: %s", path)
    return str(path)


@activity.defn
def persist_session_stats(workflow_type: str, stats: dict) -> str:
    """Saves session stats to stats/ at the end of the workflow."""
    path = stats_module.save(workflow_type, stats)
    logger.info("Stats saved: %s", path)
    return str(path)


@activity.defn
def capture_template_screen(screen_name: str, key_to_open: str = "", key_to_close: str = "") -> str:
    """Focuses the game, sends the command to open, captures the screen, and closes the menu."""
    import time

    inp.focus_game("Satisfactory")
    time.sleep(0.5)

    if key_to_open:
        inp.press(key_to_open)
        time.sleep(0.8)  # wait for the opening animation

    v = get_vision()
    frame = v.capture()
    path = save_debug_screenshot(screen_name, frame=frame)
    logger.info("Screen captured for calibration: %s", path)

    if key_to_close:
        inp.press(key_to_close)
        time.sleep(0.3)

    return str(path)


@activity.defn
def extract_templates_from_screen(screenshot_path: str, target: str = "hud", resolution: str = "2560x1440") -> dict:
    """Extracts regions of interest from the capture and saves them as new PNG templates."""
    from pathlib import Path

    import cv2

    path = Path(screenshot_path)
    if not path.exists():
        raise FileNotFoundError(f"Capture not found: {screenshot_path}")

    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"Failed to load image: {screenshot_path}")

    h, w = img.shape[:2]
    logger.info("Extracting templates for target '%s' and resolution %dx%d (config: %s)", target, w, h, resolution)

    templates_dir = Path("templates")
    templates_dir.mkdir(exist_ok=True)

    results = {}

    # Coordinates mapped for 2560x1440, with a proportional fallback
    if target == "hud":
        if w == 2560 and h == 1440:
            coords = {
                "health_low_indicator": (1330, 1380, 70, 120),  # Heart icon (health)
                # Pioneer equipment panel — only present while the inventory
                # is OPEN. The old crop was the permanent Tab HUD hint, which
                # matched ~1.0 even in gameplay (useless as an open-detector).
                "inventory_open": (192, 922, 1600, 1978),
            }
        else:
            coords = {
                "health_low_indicator": (int(h * 0.923), int(h * 0.958), int(w * 0.027), int(w * 0.047)),
                "inventory_open": (int(h * 0.133), int(h * 0.640), int(w * 0.625), int(w * 0.773)),
            }
    elif target == "workshop":
        # Note: temporary calibration coordinates for the Equipment Workshop at 2560x1440
        if w == 2560 and h == 1440:
            coords = {
                "workshop_menu_open": (50, 150, 100, 400),  # Workshop menu title (top-left)
                "rifle_ammo_icon": (400, 600, 300, 500),  # Rifle ammo icon in the menu
                "craft_button": (1000, 1200, 1800, 2200),  # Craft button (hold to fabricate)
            }
        else:
            coords = {
                "workshop_menu_open": (int(h * 0.034), int(h * 0.104), int(w * 0.039), int(w * 0.156)),
                "rifle_ammo_icon": (int(h * 0.277), int(h * 0.416), int(w * 0.117), int(w * 0.195)),
                "craft_button": (int(h * 0.694), int(h * 0.833), int(w * 0.703), int(w * 0.859)),
            }
    else:
        raise ValueError(f"Unknown extraction target: {target}")

    for name, (y1, y2, x1, x2) in coords.items():
        cropped = img[y1:y2, x1:x2]
        out_path = templates_dir / f"{name}.png"
        cv2.imwrite(str(out_path), cropped)
        results[name] = str(out_path)
        logger.info("Template '%s' extracted and saved to %s", name, out_path)

    return results


@activity.defn
def verify_matching_templates(template_names: list[str]) -> dict:
    """Scans the current screen for the templates and returns the confidence status."""
    v = get_vision()
    results = v.scan_all(template_names)

    report = {}
    for name, r in results.items():
        report[name] = {
            "found": r.found,
            "x": r.x,
            "y": r.y,
            "confidence": float(r.confidence),
        }
        logger.info("Verification of '%s': found=%s, conf=%.3f", name, r.found, r.confidence)
    return report
