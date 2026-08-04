
"""
label_captures.py

Manual classification tool: walks through the screenshots saved by
passive_capture.py (in captures/) and lets you crop regions to create
or update templates in templates/. Runs outside Temporal — a setup
tool, in the same spirit as capture_template.py, but over images
already captured instead of a live capture.

Per image, at the prompt:
    [Enter]       skip to the next one
    <name>        crop a region and save/overwrite templates/<name>.png
    d             discard the image (deletes the file)
    q             quit — progress is preserved (reviewed images go to captures/_reviewed/)

Usage:
    uv run python label_captures.py
    uv run python label_captures.py --dir captures
"""
import argparse
import os
import shutil
from pathlib import Path
from typing import Any

# The Qt bundled with cv2 only ships the "xcb" plugin — under Wayland
# sessions it tries "wayland" by default and the window ends up unable to
# receive any clicks. Force xcb (via XWayland) and disable Qt's HiDPI
# auto-scaling, which also misaligns where the click is registered.
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
os.environ.setdefault("QT_SCALE_FACTOR", "1")

import cv2

TEMPLATES_DIR = Path("templates")

# Max window size on screen — screenshots at 2560x1440+ don't fit
# entirely on most screens. cv2.selectROI maps the ROI back to the
# image's original resolution, so the saved crop stays at native
# resolution even with the window displayed smaller.
_MAX_WINDOW_W = 1600
_MAX_WINDOW_H = 900


def _show_resizable(window: str, frame: Any) -> None:
    h, w = frame.shape[:2]
    scale = min(_MAX_WINDOW_W / w, _MAX_WINDOW_H / h, 1.0)
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, int(w * scale), int(h * scale))
    cv2.imshow(window, frame)


def _crop_and_save(frame: Any, name: str) -> None:
    window = f"Crop: {name}"
    _show_resizable(window, frame)
    roi = cv2.selectROI(window, frame, fromCenter=False, showCrosshair=True)
    cv2.destroyAllWindows()
    x, y, w, h = roi
    if w == 0 or h == 0:
        print("Cancelled (no region selected).")
        return

    cropped = frame[y : y + h, x : x + w]
    out_path = TEMPLATES_DIR / f"{name}.png"
    if out_path.exists():
        resp = input(f"  '{out_path}' already exists. Overwrite? [y/N] ").strip().lower()
        if resp != "y":
            print("  Not overwritten.")
            return

    cv2.imwrite(str(out_path), cropped)
    print(f"  Saved: {out_path} ({w}x{h}px)")


def run(captures_dir: Path) -> None:
    TEMPLATES_DIR.mkdir(exist_ok=True)
    reviewed_dir = captures_dir / "_reviewed"
    reviewed_dir.mkdir(exist_ok=True, parents=True)

    images = sorted(p for p in captures_dir.glob("*.png") if p.parent == captures_dir)
    if not images:
        print(f"No images in {captures_dir}/ (run passive_capture.py first).")
        return

    print(f"{len(images)} screenshot(s) to review.\n")

    for i, img_path in enumerate(images, 1):
        frame = cv2.imread(str(img_path))
        if frame is None:
            print(f"[{i}/{len(images)}] {img_path.name} — failed to load, skipping.")
            continue

        window = "Preview — see the terminal for options"
        _show_resizable(window, frame)
        cv2.waitKey(1)

        print(f"\n[{i}/{len(images)}] {img_path.name}")
        action = input("  name to crop template | 'd' discard | Enter skip | 'q' quit: ").strip()
        cv2.destroyWindow(window)

        if action.lower() == "q":
            print("\nQuitting — progress preserved.")
            return

        if action.lower() == "d":
            img_path.unlink()
            print("  Discarded.")
            continue

        if action:
            _crop_and_save(frame, action)
            while input("  Crop another template from this image? [y/N] ").strip().lower() == "y":
                name2 = input("  template name: ").strip()
                if name2:
                    _crop_and_save(frame, name2)

        shutil.move(str(img_path), str(reviewed_dir / img_path.name))

    print(f"\nReview complete. Processed images moved to {reviewed_dir}/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual classification of captured screenshots.")
    parser.add_argument("--dir", default="captures", help="Directory with captured screenshots [captures]")
    args = parser.parse_args()
    run(Path(args.dir))


if __name__ == "__main__":
    main()
