"""
utils/screenshot.py
Salva screenshots de debug com timestamp em debug_screenshots/.
"""
import cv2
import numpy as np
import mss
from datetime import datetime
from pathlib import Path
from typing import Optional

SCREENSHOTS_DIR = Path("debug_screenshots")


def save_debug_screenshot(label: str, frame: Optional[np.ndarray] = None) -> Path:
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = SCREENSHOTS_DIR / f"{ts}_{label}.png"

    if frame is None:
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[1])
            frame = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)

    cv2.imwrite(str(path), frame)
    return path


def save_annotated_screenshot(
    label: str,
    matches: dict[str, tuple[int, int, float]],
    frame: Optional[np.ndarray] = None,
) -> Path:
    """Screenshot com círculos e labels sobre cada match encontrado."""
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = SCREENSHOTS_DIR / f"{ts}_{label}_annotated.png"

    if frame is None:
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[1])
            frame = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
    else:
        frame = frame.copy()

    for name, (x, y, conf) in matches.items():
        cv2.circle(frame, (x, y), 24, (0, 255, 0), 2)
        cv2.putText(
            frame,
            f"{name} {conf:.2f}",
            (x - 10, y - 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )

    cv2.imwrite(str(path), frame)
    return path
