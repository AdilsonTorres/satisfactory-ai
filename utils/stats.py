"""
utils/stats.py
Persists session stats to stats/{timestamp}_{workflow}.json
for later analysis.
"""

import json
from datetime import datetime
from pathlib import Path

STATS_DIR = Path("stats")
GIFT_LOG_PATH = STATS_DIR / "gift_log.jsonl"


def save(workflow_type: str, stats: dict) -> Path:
    STATS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = STATS_DIR / f"{ts}_{workflow_type}.json"

    payload = {
        "workflow_type": workflow_type,
        "saved_at": datetime.now().isoformat(),
        **stats,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return path


def log_gift_event(diff: float) -> None:
    """
    Appends one line per CONFIRMED Doggo gift transfer to stats/gift_log.jsonl.

    Used to empirically measure the real-world interval between gifts (the
    wiki gives 0.2%/second chance while the Doggo's slot is empty, i.e. a
    memoryless process averaging ~500s/8.33min — this log lets us check that
    against actual observed deltas across a live run instead of trusting the
    figure blind).
    """
    STATS_DIR.mkdir(exist_ok=True)
    record = {"ts": datetime.now().isoformat(), "slot_diff": round(diff, 2)}
    with open(GIFT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
