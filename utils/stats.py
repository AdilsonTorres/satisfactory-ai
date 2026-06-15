"""
utils/stats.py
Persiste estatísticas de sessão em stats/{timestamp}_{workflow}.json
para análise posterior.
"""
import json
from datetime import datetime
from pathlib import Path

STATS_DIR = Path("stats")


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
