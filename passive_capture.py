"""
passive_capture.py

Periodically captures screenshots while you play normally.
Sends NO input (keyboard/mouse) — safe to run in parallel with the
game while you play manually.

Frames nearly identical to the last saved one are discarded (dedup by
low-resolution diff), so it doesn't accumulate hundreds of screenshots
of the same idle menu.

After a play session, use label_captures.py to review the images in
captures/ and crop new templates or better variants of existing ones.

Usage:
    uv run python passive_capture.py
    uv run python passive_capture.py --interval 5 --max-shots 200
    uv run python passive_capture.py --dedup-threshold 0.0   # save everything, no dedup
"""
import argparse
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from utils.vision import Vision

CAPTURES_DIR = Path("captures")


def _frames_differ(a: np.ndarray, b: np.ndarray, threshold: float) -> bool:
    """Compares two downscaled frames; True if different enough to be worth saving again."""
    small_a = cv2.resize(a, (64, 36))
    small_b = cv2.resize(b, (64, 36))
    diff = cv2.absdiff(small_a, small_b)
    score = float(np.mean(diff)) / 255.0
    return score > threshold


def run(interval: float, max_shots: int, dedup_threshold: float) -> None:
    CAPTURES_DIR.mkdir(exist_ok=True)
    v = Vision()
    last_frame = None
    saved = 0

    print(f"Passive capture started — every {interval}s, saving to {CAPTURES_DIR}/")
    print("Ctrl+C to stop. No input is sent to the game — play normally.\n")

    try:
        while max_shots <= 0 or saved < max_shots:
            frame = v.capture()
            if last_frame is None or _frames_differ(frame, last_frame, dedup_threshold):
                ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
                path = CAPTURES_DIR / f"{ts}.png"
                cv2.imwrite(str(path), frame)
                saved += 1
                last_frame = frame
                print(f"[{saved}] {path.name}")
            time.sleep(interval)
    except KeyboardInterrupt:
        pass

    print(f"\nStopped. {saved} screenshot(s) saved to {CAPTURES_DIR}/")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Passive screenshot capture during manual gameplay (sends no input).",
    )
    parser.add_argument("--interval", type=float, default=4.0, help="Seconds between captures [4.0]")
    parser.add_argument("--max-shots", type=int, default=0, help="Screenshot limit, 0 = unlimited [0]")
    parser.add_argument(
        "--dedup-threshold", type=float, default=0.02,
        help="Deduplication sensitivity — 0 disables it (saves every frame) [0.02]"
    )
    args = parser.parse_args()
    run(args.interval, args.max_shots, args.dedup_threshold)


if __name__ == "__main__":
    main()
