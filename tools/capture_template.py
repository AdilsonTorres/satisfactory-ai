"""
capture_template.py

Helper script for capturing game templates.
Runs outside Temporal — it's just a setup tool.

Usage:
    uv run python capture_template.py

Press ENTER to confirm the selected region, C to cancel.
"""

import os
import time

import numpy as np

# The Qt bundled with cv2 only ships the "xcb" plugin — under Wayland
# sessions it tries "wayland" by default and the ROI selection window
# ends up unable to receive any clicks. Force xcb (via XWayland) and
# disable Qt's HiDPI auto-scaling, which also misaligns where the click
# is registered.
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
os.environ.setdefault("QT_SCALE_FACTOR", "1")

from pathlib import Path

import cv2

from utils.vision import Vision

TEMPLATES_DIR = Path("templates")
TEMPLATES_DIR.mkdir(exist_ok=True)

# Max window size on screen — screenshots at 2560x1440+ don't fit
# entirely on most screens. cv2.selectROI maps the ROI back to the
# image's original resolution, so the saved crop stays at native
# resolution even with the window displayed smaller.
_MAX_WINDOW_W = 1600
_MAX_WINDOW_H = 900

_vision = Vision()


def capture_fullscreen() -> np.ndarray:
    return _vision.capture()


def select_roi_and_save(name: str) -> bool:
    """Captures the screen and lets the user select a region with the mouse."""
    print(f"\nCapturing in 2s for template '{name}'...")
    time.sleep(2)

    frame = capture_fullscreen()
    window = f"Select: {name}"
    h, w = frame.shape[:2]
    scale = min(_MAX_WINDOW_W / w, _MAX_WINDOW_H / h, 1.0)
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, int(w * scale), int(h * scale))
    roi = cv2.selectROI(window, frame, fromCenter=False, showCrosshair=True)
    cv2.destroyAllWindows()

    x, y, w, h = roi
    if w == 0 or h == 0:
        print("Cancelled.")
        return False

    cropped = frame[y : y + h, x : x + w]
    out_path = TEMPLATES_DIR / f"{name}.png"
    cv2.imwrite(str(out_path), cropped)
    print(f"Saved: {out_path} ({w}x{h}px)")
    return True


TEMPLATES_NEEDED = [
    ("gift_prompt", "Interaction icon/text when the Doggo has a gift"),
    ("inventory_open", "Element indicating the inventory is open"),
    ("doggo_loot_window", "The Doggo's own loot window (1 slot), when interacting with E"),
    ("doggo_body", "Tamed Lizard Doggo body/face, used to aim the camera at it"),
    ("wild_doggo_prompt", "Silhouette of a wild (not yet tamed) Lizard Doggo on screen"),
    ("paleberry_icon", "Paleberry icon in the open inventory"),
    ("inventory_full_indicator", "Visual indicator that the inventory is full"),
    ("health_low_indicator", "Low health bar (red)"),
    ("equipment_workshop_prompt", "E prompt at the Equipment Workshop"),
    ("workshop_menu_open", "Element of the open Workshop menu"),
    ("rifle_ammo_icon", "Rifle Ammo icon in the craft menu"),
    ("craft_button", "Craft button in the Workshop"),
    ("enemy_spitter", "Spitter silhouette on screen"),
    ("enemy_hog", "Alpha Hog silhouette on screen"),
    ("enemy_stinger", "Stinger silhouette on screen"),
    ("enemy_spitter_elite", "Elite Spitter silhouette on screen"),
    ("enemy_hatcher", "Flying Crab Hatcher (nest) silhouette on screen"),
    ("enemy_flying_crab", "Flying Crab silhouette on screen"),
    ("enemy_hog_nuclear", "HAZARD: Nuclear/irradiated Cliff Hog — area radiation damage"),
    ("enemy_stinger_elite_gas", "HAZARD: Elite Gas Stinger — emits poison gas in an area"),
    ("enemy_remains_prompt", "E prompt to loot remains"),
    ("resource_node_prompt", "Interaction prompt when looking at a resource node in range"),
    ("storage_prompt", "Interaction prompt when looking at a storage container in range"),
    ("storage_open", "Element indicating the storage container window is open"),
    ("death_screen", "Character death screen ('Press RMB to Respawn' banner) — captured live 2026-06-25, see README"),
]


def main() -> None:
    print("=" * 60)
    print("  Satisfactory Bot — Template Capture Tool")
    print("=" * 60)
    print(f"\nSaving to: {TEMPLATES_DIR.absolute()}\n")

    for name, desc in TEMPLATES_NEEDED:
        exists = (TEMPLATES_DIR / f"{name}.png").exists()
        status = "OK" if exists else "--"
        print(f"  [{status}] {name:<35}  {desc}")

    missing = [(n, d) for n, d in TEMPLATES_NEEDED if not (TEMPLATES_DIR / f"{n}.png").exists()]

    if not missing:
        print("\nAll templates exist!")
        return

    print(f"\n{len(missing)} templates missing.")
    print("Ctrl+C at any time to continue later.\n")

    for name, desc in missing:
        print(f"{'─' * 60}")
        print(f"Template : {name}")
        print(f"What it is: {desc}")
        resp = input("Capture now? [y/N] ").strip().lower()
        if resp == "y":
            select_roi_and_save(name)

    print("\nSession finished. Templates in debug_screenshots/ to review.")
    for f in sorted(TEMPLATES_DIR.glob("*.png")):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
