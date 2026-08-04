
"""
tests/test_doggo_position.py

Unit tests for the two-phase doggo position learning system:
- _load_doggo_position / _save_doggo_position / _reset_doggo_position
- _record_miss_or_reset / _clear_miss_count
- Backwards compatibility with old yaw-only format
"""
import json
from typing import Any

import pytest

from activities.inventory import (
    _clear_miss_count,
    _load_doggo_position,
    _record_miss_or_reset,
    _reset_doggo_position,
    _save_doggo_position,
)


@pytest.fixture(autouse=True)
def _patch_paths(tmp_path: Any, monkeypatch: Any) -> Any:
    """Route all JSON persistence to a temp directory."""
    monkeypatch.setattr(
        "activities.inventory._TURN_OFFSET_PATH",
        tmp_path / "doggo_turn_offsets.json",
    )
    monkeypatch.setattr(
        "activities.inventory._MISS_COUNT_PATH",
        tmp_path / "doggo_miss_counts.json",
    )


# ── Position persistence ────────────────────────────────────────────────


def test_save_and_load_position() -> None:
    _save_doggo_position("dogginho", yaw=120, pitch=40)
    pos = _load_doggo_position("dogginho")
    assert pos == {"yaw": 120, "pitch": 40}


def test_load_returns_none_when_no_file() -> None:
    assert _load_doggo_position("unknown") is None


def test_load_returns_none_for_missing_name() -> None:
    _save_doggo_position("dogginho", 100, 50)
    assert _load_doggo_position("dogginha") is None


def test_save_overwrites_previous() -> None:
    _save_doggo_position("dogginho", 100, 50)
    _save_doggo_position("dogginho", 200, 80)
    pos = _load_doggo_position("dogginho")
    assert pos == {"yaw": 200, "pitch": 80}


def test_save_multiple_doggos() -> None:
    _save_doggo_position("dogginho", 100, 50)
    _save_doggo_position("dogginha", -80, 30)
    assert _load_doggo_position("dogginho") == {"yaw": 100, "pitch": 50}
    assert _load_doggo_position("dogginha") == {"yaw": -80, "pitch": 30}


def test_reset_removes_position() -> None:
    _save_doggo_position("dogginho", 100, 50)
    _reset_doggo_position("dogginho")
    assert _load_doggo_position("dogginho") is None


def test_reset_nonexistent_is_noop() -> None:
    """Resetting a name that doesn't exist should not raise."""
    _reset_doggo_position("nobody")


def test_reset_preserves_other_doggos() -> None:
    _save_doggo_position("dogginho", 100, 50)
    _save_doggo_position("dogginha", -80, 30)
    _reset_doggo_position("dogginho")
    assert _load_doggo_position("dogginho") is None
    assert _load_doggo_position("dogginha") == {"yaw": -80, "pitch": 30}


# ── Backwards compatibility with old yaw-only format ────────────────────


def test_load_old_yaw_only_format(tmp_path: Any) -> None:
    """Old format stored a bare int. New loader should read it as {yaw: N, pitch: 0}."""
    path = tmp_path / "doggo_turn_offsets.json"
    path.write_text(json.dumps({"dogginho": 150}))
    pos = _load_doggo_position("dogginho")
    assert pos == {"yaw": 150, "pitch": 0}


# ── Miss tracking ───────────────────────────────────────────────────────


def test_miss_counter_increments() -> None:
    """First miss should not trigger a reset."""
    assert _record_miss_or_reset("dogginho", max_misses=3) is False


def test_miss_counter_resets_after_max(tmp_path: Any) -> None:
    """After max_misses consecutive misses, position should be wiped."""
    _save_doggo_position("dogginho", 100, 50)

    # 2 misses: no reset yet
    _record_miss_or_reset("dogginho", max_misses=3)
    _record_miss_or_reset("dogginho", max_misses=3)
    assert _load_doggo_position("dogginho") == {"yaw": 100, "pitch": 50}

    # 3rd miss: triggers reset
    assert _record_miss_or_reset("dogginho", max_misses=3) is True
    assert _load_doggo_position("dogginho") is None


def test_clear_miss_count_resets_counter() -> None:
    """After clearing, the next misses should start from 0."""
    _record_miss_or_reset("dogginho", max_misses=3)
    _record_miss_or_reset("dogginho", max_misses=3)
    _clear_miss_count("dogginho")

    # Should need 3 more misses, not 1
    assert _record_miss_or_reset("dogginho", max_misses=3) is False
    assert _record_miss_or_reset("dogginho", max_misses=3) is False
    assert _record_miss_or_reset("dogginho", max_misses=3) is True


def test_miss_counter_per_doggo() -> None:
    """Miss counters are independent per doggo."""
    _record_miss_or_reset("dogginho", max_misses=2)
    _record_miss_or_reset("dogginha", max_misses=2)

    # dogginho hits 2 → reset
    assert _record_miss_or_reset("dogginho", max_misses=2) is True
    # dogginha still at 1 → no reset
    assert _record_miss_or_reset("dogginha", max_misses=2) is True
