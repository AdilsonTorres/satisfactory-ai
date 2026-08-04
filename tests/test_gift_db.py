"""Tests for utils/gift_db.py (per-doggo gift history)."""

from typing import Any

from utils import gift_db


def test_record_and_summary(tmp_path: Any) -> None:
    db = tmp_path / "gift_history.db"
    gift_db.record_check(
        "rex", collected=True, item="Power Slug", slot_diff=95.3, ts="2026-07-04T10:00:00+00:00", db_path=db
    )
    gift_db.record_check("rex", collected=False, ts="2026-07-04T10:01:00+00:00", db_path=db)
    gift_db.record_check(
        "luna", collected=True, item="Leaves", slot_diff=80.0, ts="2026-07-04T10:02:00+00:00", db_path=db
    )
    gift_db.record_check(
        "rex", collected=True, item="Power Slug", slot_diff=101.0, ts="2026-07-04T10:15:00+00:00", db_path=db
    )

    s = gift_db.summary(db_path=db)
    assert s["total_checks"] == 4
    assert s["total_gifts"] == 3
    assert s["gifts_per_doggo"] == {"rex": 2, "luna": 1}
    assert s["gifts_per_item"] == {"Power Slug": 2, "Leaves": 1}
    assert s["first_check"] == "2026-07-04T10:00:00+00:00"


def test_gift_intervals_per_doggo(tmp_path: Any) -> None:
    db = tmp_path / "gift_history.db"
    gift_db.record_check("rex", collected=True, ts="2026-07-04T10:00:00+00:00", db_path=db)
    gift_db.record_check("luna", collected=True, ts="2026-07-04T10:03:00+00:00", db_path=db)
    gift_db.record_check("rex", collected=True, ts="2026-07-04T10:10:00+00:00", db_path=db)

    assert gift_db.gift_intervals("rex", db_path=db) == [600.0]
    assert gift_db.gift_intervals("luna", db_path=db) == []


def test_empty_db_summary(tmp_path: Any) -> None:
    s = gift_db.summary(db_path=tmp_path / "empty.db")
    assert s["total_checks"] == 0
    assert s["total_gifts"] == 0
    assert s["gifts_per_doggo"] == {}
