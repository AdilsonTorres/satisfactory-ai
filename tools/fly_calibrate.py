"""
fly_calibrate.py  (one-off, scratch)

Flies the character with the Hover Pack to locate/calibrate the bottom-left
charge-ring region (gauge_subregion) and observe gauge-vs-health.

KEY CONSTRAINT (KDE Wayland, multi-monitor): input only reaches the game when
the Satisfactory window has focus, and a background script CANNOT steal focus
here. So the user must click the game window first. This script:
  1. waits `--delay` s for the user to click the game,
  2. SELF-CHECKS focus with a tiny camera nudge -- if the view doesn't move,
     the game isn't focused, so it ABORTS without sending any flight input,
  3. otherwise flies (hold Space), captures the HUD densely, descends (hold C),
     exits hover (double-tap C), and lands.
"""

import argparse
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

from utils import input as inp
from utils.vision import Vision

REGION = (0, 1050, 900, 390)  # generous bottom-left corner (x, y, w, h)
WIN_HEX = "0x06000001"


def _win():
    return subprocess.run(
        ["xdotool", "search", "--name", "Satisfactory"], capture_output=True, text=True
    ).stdout.split()[0]


def full_frame(win):
    p = subprocess.run(["import", "-window", win, "png:-"], capture_output=True)
    return cv2.imdecode(np.frombuffer(p.stdout, np.uint8), cv2.IMREAD_COLOR)


def _diff(a, b):
    return float(np.abs(a.astype(int) - b.astype(int)).mean())


def main():
    parser = argparse.ArgumentParser(description="Hover Pack flight calibration script")
    parser.add_argument("--delay", type=float, default=12.0, help="Seconds to wait before starting (default: 12)")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="debug_screenshots",
        help="Directory for calibration screenshots (default: debug_screenshots)",
    )
    args = parser.parse_args()

    delay = args.delay
    output_dir = args.output_dir
    Path(output_dir).mkdir(exist_ok=True)

    v = Vision()
    win = _win()

    print(
        f"[fly] waiting {delay:.0f}s -- CLICK the Satisfactory window now, then don't touch mouse/keyboard...",
        flush=True,
    )
    time.sleep(delay)

    subprocess.run(["wmctrl", "-i", "-a", WIN_HEX], capture_output=True)
    inp.focus_game("Satisfactory")
    time.sleep(0.4)

    # --- FOCUS SELF-CHECK (no flight input until this passes) ---
    a = full_frame(win)
    inp.move_mouse_relative(450, 0)
    time.sleep(0.25)
    b = full_frame(win)
    inp.move_mouse_relative(-450, 0)  # restore view
    time.sleep(0.2)
    fd = _diff(a, b)
    print(f"[fly] focus check: camera-sweep diff={fd:.2f}", flush=True)
    if fd < 6.0:
        print(
            "[fly] ABORT: game is NOT focused (camera did not move). "
            "No flight input sent. Click the game window and rerun.",
            flush=True,
        )
        return

    print("[fly] focus OK -- proceeding to fly.", flush=True)

    def snap(tag, full=False):
        g = v.grab_region(*REGION)
        cv2.imwrite(f"{output_dir}/cal_{tag}.png", g)
        if full:
            cv2.imwrite(f"{output_dir}/cal_{tag}_full.png", full_frame(win))
        st = v.read_player_status()
        print(
            f"[fly] {tag}: hp={st['health_segments']}/10 gauge={st['gauge_frac']} "
            f"dmg={st['damage_red']:.3f} died={st['died']}",
            flush=True,
        )
        return st

    snap("00_ground", full=True)

    # START FLIGHT: hold Space; snap densely during the hold
    inp.keys_down(["space"])
    try:
        for i in range(6):  # ~2.4s holding space
            time.sleep(0.4)
            snap(f"01_rise_{i}", full=(i == 5))
    finally:
        inp.keys_up(["space"])
    time.sleep(0.2)
    snap("02_hover", full=True)

    # drift forward while keeping altitude
    inp.keys_down(["w", "space"])
    try:
        for i in range(4):
            time.sleep(0.5)
            snap(f"03_move_{i}")
    finally:
        inp.keys_up(["w", "space"])

    # DESCEND: hold C
    inp.keys_down(["c"])
    try:
        for i in range(4):
            time.sleep(0.4)
            snap(f"04_descend_{i}")
    finally:
        inp.keys_up(["c"])

    # EXIT hover: double-tap C
    inp.tap_key("c")
    time.sleep(0.12)
    inp.tap_key("c")
    time.sleep(0.6)
    snap("05_landed", full=True)

    print("[fly] done. final status:", v.read_player_status(), flush=True)


if __name__ == "__main__":
    main()
