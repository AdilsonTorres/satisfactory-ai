"""
utils/gift_db.py

Persistent per-doggo gift history in SQLite (stats/gift_history.db).

Every check is recorded — found or empty — so the real distribution of
time-between-gifts per doggo can be measured (is the cycle interval too
long? too short?), and items/hour, totals per item, etc. can be reported
later straight from SQL.

Written by the record_gift_check activity (persist queue / Docker worker);
read by ad-hoc analysis or future report tooling.
"""

import sqlite3
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

DB_PATH = Path("stats") / "gift_history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gift_checks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,              -- ISO-8601 UTC
    doggo      TEXT NOT NULL,              -- doggo name from [[taming.doggos]]
    collected  INTEGER NOT NULL,           -- 1 = a gift was actually transferred
    item       TEXT,                       -- OCR'd item name (NULL if empty/unknown)
    slot_diff  REAL,                       -- before/after pixel diff of the loot slot
    crop_path  TEXT                        -- saved slot icon crop, for later labeling
);
CREATE INDEX IF NOT EXISTS idx_gift_checks_doggo_ts ON gift_checks (doggo, ts);
"""


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def record_check(
    doggo: str,
    collected: bool,
    item: str | None = None,
    slot_diff: float | None = None,
    crop_path: str | None = None,
    ts: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Append one gift-check observation (found or empty)."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO gift_checks (ts, doggo, collected, item, slot_diff, crop_path) VALUES (?, ?, ?, ?, ?, ?)",
            (
                ts or datetime.now(UTC).isoformat(timespec="seconds"),
                doggo,
                int(collected),
                item,
                round(slot_diff, 2) if slot_diff is not None else None,
                crop_path,
            ),
        )


def gift_intervals(doggo: str, db_path: Path | None = None) -> list[float]:
    """Seconds between consecutive COLLECTED gifts for one doggo (analysis helper)."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT ts FROM gift_checks WHERE doggo = ? AND collected = 1 ORDER BY ts",
            (doggo,),
        ).fetchall()
    times = [datetime.fromisoformat(r[0]) for r in rows]
    return [(b - a).total_seconds() for a, b in pairwise(times)]


def summary(db_path: Path | None = None) -> dict:
    """Totals per doggo and per item — the raw material for reports."""
    with _connect(db_path) as conn:
        per_doggo = dict(conn.execute("SELECT doggo, SUM(collected) FROM gift_checks GROUP BY doggo").fetchall())
        per_item = dict(
            conn.execute(
                "SELECT item, COUNT(*) FROM gift_checks WHERE collected = 1 AND item IS NOT NULL GROUP BY item"
            ).fetchall()
        )
        first_last = conn.execute("SELECT MIN(ts), MAX(ts), SUM(collected), COUNT(*) FROM gift_checks").fetchone()
    return {
        "gifts_per_doggo": per_doggo,
        "gifts_per_item": per_item,
        "first_check": first_last[0],
        "last_check": first_last[1],
        "total_gifts": first_last[2] or 0,
        "total_checks": first_last[3],
    }
