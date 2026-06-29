"""
gauge_record.py  (one-off, scratch)

Passive (read-only) recorder: samples the Hover Pack charge gauge + health +
damage vignette while the user flies, then renders a cv2 timeline chart. Sends
NO input, so it cannot affect the character -- safe to run while supervised.
Used to study the gauge-vs-health relationship for death analysis.
"""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from utils.vision import Vision


def main():
    parser = argparse.ArgumentParser(description="Hover Pack gauge recorder")
    parser.add_argument("--duration", type=float, default=45.0, help="Recording duration in seconds (default: 45)")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="debug_screenshots",
        help="Directory for output files (default: debug_screenshots)",
    )
    args = parser.parse_args()

    dur = args.duration
    output_dir = args.output_dir
    Path(output_dir).mkdir(exist_ok=True)

    v = Vision()
    samples = []
    t0 = time.time()
    print(f"[rec] sampling {dur:.0f}s ...", flush=True)
    while time.time() - t0 < dur:
        st = v.read_player_status()
        t = time.time() - t0
        samples.append(
            {
                "t": round(t, 2),
                "gauge": st["gauge_frac"],
                "health": st["health_frac"],
                "dmg": round(st["damage_red"], 3),
                "died": st["died"],
            }
        )
        flying = st["gauge_frac"] is not None
        print(
            f"[rec] t={t:5.1f}s gauge={st['gauge_frac']} hp={st['health_frac']:.1f} "
            f"dmg={st['damage_red']:.3f} {'FLYING' if flying else 'grounded'}",
            flush=True,
        )
        if st["died"]:
            print("[rec] DEATH detected -- recording the fall.", flush=True)
        time.sleep(0.25)

    with open(f"{output_dir}/gauge_timeline.json", "w") as f:
        json.dump(samples, f, indent=2)

    # --- render chart ---
    W, H = 1100, 460
    img = np.full((H, W, 3), 30, np.uint8)
    pad = 60
    n = len(samples)
    if n > 1:

        def X(i):
            return int(pad + (W - 2 * pad) * i / (n - 1))

        def Y(frac):
            return int((H - pad) - (H - 2 * pad) * frac)

        # gridlines + labels
        for f in (0, 0.25, 0.5, 0.75, 1.0):
            yy = Y(f)
            cv2.line(img, (pad, yy), (W - pad, yy), (60, 60, 60), 1)
            cv2.putText(img, f"{f:.2f}", (8, yy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        # series
        for key, color, _default in (
            ("health", (0, 220, 0), 0.0),
            ("gauge", (0, 165, 255), None),
            ("dmg", (0, 0, 230), 0.0),
        ):
            pts = []
            for i, s in enumerate(samples):
                val = s[key]
                if val is None:
                    pts.append(None)
                    continue
                val = min(val, 1.0) if key != "dmg" else min(val * 3, 1.0)  # scale dmg x3
                pts.append((X(i), Y(val)))
            for i in range(1, n):
                if pts[i - 1] and pts[i]:
                    cv2.line(img, pts[i - 1], pts[i], color, 2)
        # legend
        cv2.putText(img, "health", (pad, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 0), 2)
        cv2.putText(img, "gauge", (pad + 130, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
        cv2.putText(img, "dmg x3", (pad + 250, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 230), 2)
        cv2.putText(
            img, f"t=0..{samples[-1]['t']:.0f}s", (W - 200, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2
        )
    cv2.imwrite(f"{output_dir}/gauge_timeline.png", img)

    # --- summary ---
    flying = [s for s in samples if s["gauge"] is not None]
    print("\n[rec] === summary ===", flush=True)
    print(f"[rec] samples={n}  flying={len(flying)}  grounded={n - len(flying)}", flush=True)
    if flying:
        gs = [s["gauge"] for s in flying]
        print(f"[rec] gauge while flying: min={min(gs):.2f} max={max(gs):.2f}", flush=True)
    hmin = min(s["health"] for s in samples)
    print(f"[rec] health min={hmin:.1f}  any-death={any(s['died'] for s in samples)}", flush=True)
    print("[rec] saved gauge_timeline.json + gauge_timeline.png", flush=True)


if __name__ == "__main__":
    main()
