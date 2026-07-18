"""
utils/stats.py
Persists session stats to stats/{timestamp}_{workflow}.json
using Pydantic for validation and fast serialization.
"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

STATS_DIR = Path("stats")


class SessionStats(BaseModel):
    model_config = ConfigDict(extra="allow")

    workflow_type: str
    saved_at: datetime


def save(workflow_type: str, stats: dict) -> Path:
    STATS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = STATS_DIR / f"{ts}_{workflow_type}.json"

    # Validate using Pydantic
    model = SessionStats(workflow_type=workflow_type, saved_at=datetime.now(), **stats)

    # Write using Pydantic's optimized JSON serialization
    with open(path, "w", encoding="utf-8") as f:
        f.write(model.model_dump_json(indent=2))

    return path
