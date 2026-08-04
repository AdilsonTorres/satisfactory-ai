"""
activities/inventory.py

Inventory and Doggo gift activities.
"""

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from temporalio import activity

from utils import config as cfg
from utils import input as inp
from utils.exceptions import MenuError, VisionError
from utils.vision import MatchResult, Vision, ocr_text

from ._shared import (
    MENU_TOGGLE_ATTEMPTS,
    close_open_menus,
    get_vision,
    press_until_closed,
    press_until_open,
    screenshot_on_error,
)

logger = logging.getLogger(__name__)

# Kept as a module alias for readability at call sites; the verified
# open/close primitives now live in activities/_shared.py so every activity
# module shares one hardened key-press path.
_OPEN_WINDOW_ATTEMPTS = MENU_TOGGLE_ATTEMPTS
_press_until_window_open = press_until_open


def _gift_prompt_region(sw: int, sh: int) -> tuple[int, int, int, int]:
    """
    Screen rectangle where the 'Press E … Lizard Doggo …' prompt renders.

    The prompt is a UI band anchored to the crosshair, NOT to the Doggo's
    world position: it's horizontally centred and sits ~9% of the screen
    height below centre (measured live 2026-06-30 at 2560x1440: the 740x50
    band landed at x 920-1660, y 785-835). Returning a snug band lets us
    detect it with a ~0.2s cropped grab instead of a ~7.5s full frame.
    """
    cx = sw // 2
    cy = int(sh * 0.5625)
    half_w, margin_y = 540, 70
    x = max(0, cx - half_w)
    y = max(0, cy - margin_y)
    return (x, y, min(sw - x, 2 * half_w), min(sh - y, 2 * margin_y))


def _camera_responds(v: Vision) -> float | None:
    """
    Returns the measured mouse sensitivity factor (pixels per relative unit)
    if the gameplay camera actually turns when we send a relative mouse move.
    Returns None if the camera is frozen or not responding.
    """
    disp = cfg.get("display", {})
    sw = disp.get("screen_width", 1920)
    sh = disp.get("screen_height", 1080)
    # A central patch grabbed with the fast cropped path (~0.2s); a full-frame
    # capture would cost ~7.5s per probe.
    px, py, pw, ph = sw // 2 - 300, sh // 2 - 200, 600, 400
    window = cv2.createHanningWindow((pw, ph), cv2.CV_32F)

    def _luma() -> np.ndarray:
        return cv2.cvtColor(v.grab_region(px, py, pw, ph), cv2.COLOR_BGR2GRAY).astype(np.float32)

    for attempt in range(2):
        before = _luma()
        inp.move_mouse_relative(300, 0)
        time.sleep(0.25)
        after = _luma()
        inp.move_mouse_relative(-300, 0)  # undo the probe
        time.sleep(0.15)
        (shift_x, _), _ = cv2.phaseCorrelate(before, after, window)
        if abs(shift_x) > 5.0:  # in-place animation reads ~0; a real turn shifts many px
            return float(abs(shift_x) / 300.0)
        logger.debug("Camera probe %d: x-shift %.2fpx (frozen) — recapturing.", attempt, shift_x)
        inp.ensure_game_input_ready()
        time.sleep(0.2)
    return None


def _reset_pitch_to_home(v: Vision, sensitivity: float | None = None) -> None:
    """
    Snap the camera pitch to a known 'home' baseline: slightly below the
    horizon, where Lizard Doggos (ground creatures) are most likely to be
    visible. Works by pitching hard upward to hit the engine's pitch clamp
    (looking straight up — a fixed, known state), then pitching down by a
    configured amount to reach the baseline.

    This eliminates accumulated pitch drift between cycles and guarantees
    that subsequent sweeps never waste time searching the sky. The yaw is
    left untouched (it wraps, so there's no equivalent clamp trick).
    """
    sens = sensitivity if sensitivity is not None else 2.0
    # Pitch hard up to hit the clamp (~90° up). At ~2.0 sens, 1400 relative
    # units moves ~700px ≈ well past the ~45° limit in Satisfactory.
    up_amount = int(1400.0 / sens)
    inp.move_mouse_relative(0, -up_amount)
    time.sleep(0.15)
    # Now pitch down from the clamp to our home baseline. Configured as
    # taming.home_pitch_down (positive = look down). Default 400 at sens=2.0
    # ≈ 200px ≈ ~25° below zenith ≈ slightly below horizon for a standing
    # player in the doggo pen.
    home_down = int(cfg.get("taming.home_pitch_down", 400) / sens)
    inp.move_mouse_relative(0, home_down)
    time.sleep(0.15)


def _face_doggo_and_recheck(v: Vision, sensitivity: float | None = None) -> tuple[MatchResult, int, int]:
    """
    Discovery sweep: reset the camera to a known 'home' pitch, then sweep
    yaw x downward-pitch rows to find the 'gift_prompt' UI band.

    Returns (result, net_yaw, net_pitch) — the camera offsets FROM HOME
    where the doggo was found (both 0 on a miss, since the camera is
    restored). On a HIT the camera is left on-target so the caller can
    interact immediately and record the position.

    Key improvements over the original:
    - Resets pitch to home first → never searches the sky.
    - Returns net_yaw AND net_pitch → caller can save both for the
      locked-position fast path on subsequent cycles.
    - Pitch rows only go DOWNWARD from home (doggos are ground creatures).
    """
    disp = cfg.get("display", {})
    sw = disp.get("screen_width", 1920)
    sh = disp.get("screen_height", 1080)
    region = _gift_prompt_region(sw, sh)

    # Mouse-look only reaches the game when it holds real KWin input focus.
    inp.focus_game()

    sens = sensitivity if sensitivity is not None else _camera_responds(v)
    if sens is None:
        logger.warning("Camera not responding to mouse-look — cannot sweep for the Doggo.")
        return v.find_in_region("gift_prompt", region), 0, 0

    # Reset pitch to home baseline before sweeping — eliminates drift and
    # ensures we never waste time searching the sky.
    _reset_pitch_to_home(v, sens)

    # Check at home position before starting the expensive sweep.
    gp = v.find_in_region("gift_prompt", region)
    if gp.found:
        logger.info("Gift prompt at home position (conf=%.2f).", gp.confidence)
        return gp, 0, 0

    # Calculate dynamic yaw step based on measured sensitivity.
    # Target a 360-pixel shift per step (covers the 740px prompt width with ample overlap).
    yaw_step = int(360.0 / sens)
    yaw_count = int(cfg.get("taming.search_yaw_count", 8))
    # Pitch rows are DOWNWARD only (positive = look down). First row is 0
    # (home pitch), subsequent rows step further down.
    pitch_rows = cfg.get("taming.search_pitch_rows", [0, 160, 160])

    net_pitch = 0
    for pitch in pitch_rows:
        if pitch:
            inp.move_mouse_relative(0, pitch)
            net_pitch += pitch
            time.sleep(0.2)
        net_yaw = 0
        for _ in range(yaw_count):
            gp = v.find_in_region("gift_prompt", region)
            if gp.found:
                logger.info("Gift prompt acquired (conf=%.2f) after sweep.", gp.confidence)
                return gp, net_yaw, net_pitch  # leave camera on-target
            inp.move_mouse_relative(yaw_step, 0)
            net_yaw += yaw_step
            time.sleep(0.12)
        inp.move_mouse_relative(-net_yaw, 0)  # back to this row's yaw origin
        time.sleep(0.15)

    # Exhausted every row with no hit — restore to home pitch.
    if net_pitch:
        inp.move_mouse_relative(0, -net_pitch)
        time.sleep(0.15)

    return v.find_in_region("gift_prompt", region), 0, 0


def _micro_sweep_for_prompt(
    v: Vision,
    region: tuple[int, int, int, int],
    sensitivity: float | None = None,
) -> tuple[MatchResult, int]:
    """
    Small yaw and pitch sweep around the CURRENT facing to re-acquire 'gift_prompt' —
    alternating right/left. If not found, pitches down slightly and sweeps again.
    Used after turning to a doggo whose configured/learned turn_dx is a little off
    (doggos wander a few steps between checks). Leaves the camera where the prompt
    was found.

    Returns (result, net_yaw_applied).
    """
    sens = sensitivity if sensitivity is not None else 2.0
    step = int(80.0 / sens)
    count = int(cfg.get("taming.micro_yaw_count", 4))
    pitch_step = int(160.0 / sens)

    # 1. Check current facing first
    gp = v.find_in_region("gift_prompt", region)
    if gp.found:
        return gp, 0

    net_yaw = 0
    net_pitch = 0

    try:
        # Alternating yaw offsets: +1, -1, +2, -2, ... +count, -count
        offsets = []
        for i in range(1, count + 1):
            offsets.append(i)
            offsets.append(-i)

        # Row 1: Current pitch (0)
        for offset in offsets:
            target_yaw = offset * step
            delta = target_yaw - net_yaw
            inp.move_mouse_relative(delta, 0)
            net_yaw = target_yaw
            time.sleep(0.1)

            gp = v.find_in_region("gift_prompt", region)
            if gp.found:
                return gp, net_yaw

        # Recenter yaw
        if net_yaw != 0:
            inp.move_mouse_relative(-net_yaw, 0)
            net_yaw = 0
            time.sleep(0.1)

        # Row 2: Look down slightly
        inp.move_mouse_relative(0, pitch_step)
        net_pitch += pitch_step
        time.sleep(0.12)

        # Check center at lower pitch
        gp = v.find_in_region("gift_prompt", region)
        if gp.found:
            return gp, 0

        # Alternating yaw sweep at lower pitch (smaller count is sufficient)
        lower_count = min(3, count)
        for offset in offsets[: 2 * lower_count]:
            target_yaw = offset * step
            delta = target_yaw - net_yaw
            inp.move_mouse_relative(delta, 0)
            net_yaw = target_yaw
            time.sleep(0.1)

            gp = v.find_in_region("gift_prompt", region)
            if gp.found:
                return gp, net_yaw

        # Recenter yaw for Row 2
        if net_yaw != 0:
            inp.move_mouse_relative(-net_yaw, 0)
            net_yaw = 0
            time.sleep(0.1)

    finally:
        # If we didn't find the doggo, restore the pitch/yaw so we don't leave the camera displaced
        if not gp.found:
            if net_yaw != 0:
                inp.move_mouse_relative(-net_yaw, 0)
            if net_pitch != 0:
                inp.move_mouse_relative(0, -net_pitch)
            time.sleep(0.1)

    return v.find_in_region("gift_prompt", region), 0


def _any_doggo_name_matches(ocr_name: str, expected_names: list[str]) -> str | None:
    for expected in expected_names:
        if _doggo_name_matches(ocr_name, expected):
            return expected
    return None


def _doggo_name_matches(ocr_name: str, expected_name: str) -> bool:
    """
    Tolerant OCR-name compare: startswith rather than exact equality, since
    the title OCR occasionally trails a stray character or word off a
    genuinely correct read (measured live: 'dogginha e' for 'dogginha'),
    which an exact match rejected — sending a correctly-found doggo into a
    pointless (and camera-displacing) active search. The two roster names
    diverge at their first differing character ('dogginh-o' vs 'dogginh-a'),
    so startswith can't cross-confuse them.
    """
    if not ocr_name:
        return False
    ocr = ocr_name.strip().lower()
    exp = expected_name.strip().lower()
    if ocr.startswith(exp) or exp in ocr:
        return True
    # Handle single character typos at the end (e.g. dogginha7, dogginh4, dogginh0)
    if len(exp) > 1 and ocr.startswith(exp[:-1]):
        last_char_exp = exp[-1]
        last_char_ocr = ocr[len(exp) - 1 :] if len(ocr) >= len(exp) else ""
        if last_char_ocr:
            c = last_char_ocr[0]
            if last_char_exp == "a" and c in "a4q@7bhnr":
                return True
            if last_char_exp == "o" and c in "o0u9dpfwi":
                return True
    return False


def _read_loot_window_doggo_name(v: Vision) -> str:
    """
    OCR the loot window's title bar — the doggo's REAL in-game name, and
    the only authoritative way to know which doggo we actually opened
    (there's no in-world nameplate before interacting). Returns '' if
    nothing legible was read.
    """
    nx = int(cfg.get("taming.name_region_x", 740))
    ny = int(cfg.get("taming.name_region_y", 180))
    nw = int(cfg.get("taming.name_region_w", 560))
    nh = int(cfg.get("taming.name_region_h", 60))
    title = ocr_text(v.grab_region(nx, ny, nw, nh))
    for line in title.splitlines():
        cleaned = "".join(ch for ch in line if ch.isalnum() or ch in " -'").strip()
        if len(cleaned) >= 3:
            return cleaned
    return ""


def _search_for_named_doggo(
    v: Vision,
    region: tuple[int, int, int, int],
    expected_names: list[str],
    sensitivity: float | None = None,
) -> tuple[MatchResult | None, str, int, int]:
    """
    Actively hunt for a SPECIFIC doggo by name, used when the loot window
    that opened is the WRONG one. Doggos wander independently — a fixed or
    previously-learned turn_dx can go stale enough to miss the target
    entirely (measured live: an entire overnight run had 'dogginha's turn
    landing on 'dogginho' 479/479 times). Silently accepting whichever
    doggo is in frame would just keep re-checking the same one.

    Two phases. First, a FINE yaw-only zigzag close to the current facing:
    two doggos sitting close together can be a SMALL lateral offset apart
    (measured live 2026-07-06: dogginho sat just barely to the right of
    dogginha) that a coarse search jumps straight over. Only if that fails
    does it escalate to a coarser grid sweep — a few downward pitch rows,
    each swept across yaw (same shape as _face_doggo_and_recheck) — for a
    doggo that's wandered further. Opens each candidate's window to verify
    the title; every wrong window is closed before continuing.

    Returns (confirm, ocr_name, net_yaw, net_pitch): on success confirm is
    the loot window MatchResult and its window is left OPEN for the caller
    to collect from, with the camera deliberately left on-target; on
    failure confirm is None and the camera (yaw AND pitch) is restored to
    where it started (a stranded camera after a failed search is what left
    a doggo undetectable for the rest of a run — measured live 2026-07-05:
    dogginha's offset got saved mid-failed-search and then missed for 7+
    hours straight with no recovery). net_yaw/net_pitch are the total
    relative movement applied here (0 on failure, since it's undone).
    """
    inp.focus_game()

    sens = sensitivity if sensitivity is not None else _camera_responds(v)
    if sens is None:
        sens = 2.0  # Fallback to standard baseline if camera calibration is unavailable

    fine_step = int(40.0 / sens)
    fine_count = int(cfg.get("taming.identify_fine_yaw_count", 10))

    # Check center first
    gp = v.find_in_region("gift_prompt", region)
    if gp.found:
        confirm = _press_until_window_open(v, "doggo_loot_window")
        if confirm.found:
            ocr_name = _read_loot_window_doggo_name(v)
            if _any_doggo_name_matches(ocr_name, expected_names):
                return confirm, ocr_name, 0, 0
            press_until_closed(v, "doggo_loot_window")

    net_yaw = 0
    offsets = []
    for i in range(1, fine_count + 1):
        offsets.append(i)
        offsets.append(-i)

    for offset in offsets:
        target_yaw = offset * fine_step
        delta = target_yaw - net_yaw
        inp.move_mouse_relative(delta, 0)
        net_yaw = target_yaw
        time.sleep(0.1)

        gp = v.find_in_region("gift_prompt", region)
        if gp.found:
            confirm = _press_until_window_open(v, "doggo_loot_window")
            if confirm.found:
                ocr_name = _read_loot_window_doggo_name(v)
                if _any_doggo_name_matches(ocr_name, expected_names):
                    return confirm, ocr_name, net_yaw, 0
                press_until_closed(v, "doggo_loot_window")

    if net_yaw != 0:
        inp.move_mouse_relative(-net_yaw, 0)
        time.sleep(0.1)

    yaw_step = int(360.0 / sens)
    yaw_count = int(cfg.get("taming.search_yaw_count", 8))
    pitch_rows = [int(p * 2.0 / sens) for p in cfg.get("taming.search_pitch_rows", [0, 160, 160])]

    net_pitch = 0
    for pitch in pitch_rows:
        if pitch:
            inp.move_mouse_relative(0, pitch)
            net_pitch += pitch
            time.sleep(0.2)
        net_yaw = 0
        for _ in range(yaw_count):
            gp = v.find_in_region("gift_prompt", region)
            if gp.found:
                confirm = _press_until_window_open(v, "doggo_loot_window")
                if confirm.found:
                    ocr_name = _read_loot_window_doggo_name(v)
                    if _any_doggo_name_matches(ocr_name, expected_names):
                        return confirm, ocr_name, net_yaw, net_pitch
                    press_until_closed(v, "doggo_loot_window")
            inp.move_mouse_relative(yaw_step, 0)
            net_yaw += yaw_step
            time.sleep(0.12)
        inp.move_mouse_relative(-net_yaw, 0)
        time.sleep(0.15)

    if net_pitch:
        inp.move_mouse_relative(0, -net_pitch)
        time.sleep(0.15)
    return None, "", 0, 0


_TURN_OFFSET_PATH = Path("stats") / "doggo_turn_offsets.json"


def _load_doggo_position(name: str) -> dict[str, Any] | None:
    """
    Load a doggo's learned camera position (yaw + pitch offsets from home).

    Returns {"yaw": int, "pitch": int} if a position was previously saved,
    or None if no learned position exists. Backwards-compatible: if the
    stored value is a bare int (old yaw-only format), it's read as
    {"yaw": value, "pitch": 0}.

    Positions are ABSOLUTE offsets from the "home" camera orientation
    (pitch reset to slightly below horizon via _reset_pitch_to_home)
    rather than relative to the previous doggo. This decouples the
    doggos from each other: finding doggo A no longer depends on where
    the camera ended up after checking doggo B.
    """
    try:
        with open(_TURN_OFFSET_PATH, encoding="utf-8") as f:
            data = json.load(f)
        val = data.get(name)
        if val is None:
            return None
        # Backwards compat: old format stored a bare int (yaw only)
        if isinstance(val, int | float):
            return {"yaw": int(val), "pitch": 0}
        if isinstance(val, dict) and "yaw" in val:
            return {"yaw": int(val["yaw"]), "pitch": int(val.get("pitch", 0))}
        return None
    except FileNotFoundError, json.JSONDecodeError, ValueError:
        return None


def _save_doggo_position(name: str, yaw: int, pitch: int) -> None:
    """Persist a doggo's camera position (yaw + pitch from home)."""
    _TURN_OFFSET_PATH.parent.mkdir(exist_ok=True)
    data: dict[str, Any] = {}
    try:
        with open(_TURN_OFFSET_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError, json.JSONDecodeError:
        pass
    data[name] = {"yaw": yaw, "pitch": pitch}
    with open(_TURN_OFFSET_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _reset_doggo_position(name: str) -> None:
    """Drop a doggo's learned position so the next cycle re-discovers it."""
    try:
        with open(_TURN_OFFSET_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError, json.JSONDecodeError:
        return
    if data.pop(name, None) is not None:
        with open(_TURN_OFFSET_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


# Legacy alias — kept for any external callers.
_load_turn_offset = lambda name: pos["yaw"] if (pos := _load_doggo_position(name)) else None  # noqa: E731
_save_turn_offset = lambda name, yaw: _save_doggo_position(name, yaw, 0)  # noqa: E731
_reset_turn_offset = _reset_doggo_position


_MISS_COUNT_PATH = Path("stats") / "doggo_miss_counts.json"


def _record_miss_or_reset(name: str, max_misses: int) -> bool:
    """
    Tracks consecutive 'no gift prompt visible' misses for ANY doggo.
    After max_misses in a row, drops the learned position
    (_reset_doggo_position) so the next cycle re-discovers instead of
    repeating the same dead angle forever. Returns True if a reset just
    happened.
    """
    _MISS_COUNT_PATH.parent.mkdir(exist_ok=True)
    data: dict[str, Any] = {}
    try:
        with open(_MISS_COUNT_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError, json.JSONDecodeError:
        pass
    misses = int(data.get(name, 0)) + 1
    reset = misses >= max_misses
    data[name] = 0 if reset else misses
    with open(_MISS_COUNT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    if reset:
        _reset_doggo_position(name)
    return reset


def _clear_miss_count(name: str) -> None:
    try:
        with open(_MISS_COUNT_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError, json.JSONDecodeError:
        return
    if data.get(name, 0) != 0:
        data[name] = 0
        with open(_MISS_COUNT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


_EMPTY_SLOT_REF_DIR = Path("templates")
_empty_slot_refs: dict[str, tuple[float, np.ndarray]] = {}


def _empty_ref_key(doggo_name: str) -> str:
    return "".join(ch for ch in doggo_name.lower() if ch.isalnum() or ch in "-_") or "default"


def _empty_slot_reference(doggo_name: str) -> np.ndarray | None:
    """
    Per-doggo reference capture of the EMPTY loot slot patch. Lets
    collect_doggo_gift skip the ~8s cursor walk + hover on the ~90% of
    checks where the slot is empty. A reference DIFF is used instead of a
    brightness heuristic because dark item icons (e.g. Cable, measured
    2026-07-04) would read as 'empty' on brightness and be skipped forever.

    The loot window is translucent, so the world behind it bleeds into the
    patch: references are per-doggo AND self-refreshing — every full-path
    check that confirms an empty slot re-saves the reference (see
    _refresh_empty_slot_reference), because the doggos wander and the
    backdrop drifts (measured live 2026-07-05: a fresh ref went stale
    within two cycles). References older than empty_ref_max_age_seconds
    are ignored, which bounds both staleness and any mis-saved reference.
    A missing/stale ref only means the full walk runs — never a wrong skip.
    """
    key = _empty_ref_key(doggo_name)
    path = _EMPTY_SLOT_REF_DIR / f"loot_slot_empty_{key}.png"
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    if time.time() - mtime > float(cfg.get("taming.empty_ref_max_age_seconds", 3600)):
        return None
    cached = _empty_slot_refs.get(key)
    if cached is None or cached[0] != mtime:
        img = cv2.imread(str(path))
        if img is None:
            return None
        _empty_slot_refs[key] = (mtime, img)
    return _empty_slot_refs[key][1]


def _refresh_empty_slot_reference(doggo_name: str, patch: np.ndarray) -> None:
    """Save `patch` (grabbed PRE-walk, so no cursor overlay) as the doggo's
    empty-slot reference. Called only after a full-path check confirmed the
    slot empty (no tooltip band after retries AND a no-op transfer diff)."""
    key = _empty_ref_key(doggo_name)
    _EMPTY_SLOT_REF_DIR.mkdir(exist_ok=True)
    cv2.imwrite(str(_EMPTY_SLOT_REF_DIR / f"loot_slot_empty_{key}.png"), patch)
    _empty_slot_refs.pop(key, None)


def _tooltip_band_visible(crop: np.ndarray) -> bool:
    """
    True if the tooltip's ORANGE item-name header band is actually rendered
    in the crop (top rows). Without this check, OCR happily reads whatever
    UI sits under the tooltip region (measured live 2026-07-04: the 'Sort'
    button OCR'd as 'I sSort' and got persisted as an item name) — the
    tooltip render often lags the hover by more than the initial wait.
    """
    band = crop[5:45]
    b = float(band[..., 0].mean())
    g = float(band[..., 1].mean())
    r = float(band[..., 2].mean())
    return r > 150 and (r - b) > 80 and g > 90


def _read_item_tooltip(v: Vision, slot_x: int, slot_y: int) -> tuple[str | None, np.ndarray]:
    """
    Grab the item tooltip shown while hovering the loot slot and OCR the
    item name (first legible line). Returns (name_or_None, tooltip_crop).
    The crop region is cursor-relative and configured under [taming]
    tooltip_*. Waits for the orange header band to actually render (with a
    cursor-nudge retry — the hover event sometimes needs fresh mouse motion)
    and returns None rather than OCR'ing unrelated UI when it never shows
    (empty slot, or tooltip too slow).
    """
    tdx = int(cfg.get("taming.tooltip_dx", 30))
    tdy = int(cfg.get("taming.tooltip_dy", 10))
    tw = int(cfg.get("taming.tooltip_w", 520))
    th = int(cfg.get("taming.tooltip_h", 140))
    sw = int(cfg.get("display.screen_width", 2560))
    sh = int(cfg.get("display.screen_height", 1440))
    x = min(max(0, slot_x + tdx), sw - tw)
    y = min(max(0, slot_y + tdy), sh - th)
    crop = v.grab_region(x, y, tw, th)
    # 3 attempts ~0.5s apart: measured live 2026-07-04, the tooltip can lag
    # the hover by well over a second (two real transfers had it still
    # mid-render at click time), and each retry only costs time when the
    # slot actually holds an item.
    for _ in range(3):
        if _tooltip_band_visible(crop):
            text = ocr_text(crop)
            for line in text.splitlines():
                cleaned = "".join(ch for ch in line if ch.isalnum() or ch in " -'").strip()
                if len(cleaned) >= 3:
                    return cleaned, crop
            return None, crop
        # No band yet — nudge the cursor to (re)trigger hover and give the
        # tooltip more time to render.
        inp.move_mouse_relative(3, 3)
        time.sleep(0.05)
        inp.move_mouse_relative(-3, -3)
        time.sleep(0.45)
        crop = v.grab_region(x, y, tw, th)
    return None, crop


@activity.defn
def collect_doggo_gift(doggo: Any = None) -> dict[str, Any]:
    """
    Check ONE named doggo (or a list of unchecked doggos) for a gift and
    collect it if present.

    Two-phase navigation:
    1. LOCKED: if a saved position exists for this doggo, reset camera to
       home pitch, apply the saved yaw+pitch offset, then micro-sweep.
       This is fast (~1s) and finds the doggo >95% of the time.
    2. DISCOVERY: if no saved position, or the locked phase missed, run
       a full pitch/yaw sweep from home. On success, save the discovered
       position for future locked-phase use.

    After max_consecutive_misses (default 3), the saved position is wiped
    and the next cycle re-enters discovery mode.
    """
    if isinstance(doggo, list):
        expected_names = []
        for item in doggo:
            if isinstance(item, dict):
                expected_names.append(str(item.get("name", "doggo")))
            else:
                expected_names.append(str(item))
        name = expected_names[0] if expected_names else "doggo"
    else:
        spec = doggo or {}
        name = str(spec.get("name", "doggo"))
        expected_names = [name]

    # Load saved position (yaw + pitch from home baseline).
    saved_pos = _load_doggo_position(name)

    result: dict[str, Any] = {
        "doggo": name,
        "prompt_found": False,
        "collected": False,
        "item": None,
        "slot_diff": None,
        "crop_path": None,
        "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    with screenshot_on_error("collect_doggo_gift"):
        v = get_vision()
        disp = cfg.get("display", {})
        region = _gift_prompt_region(disp.get("screen_width", 1920), disp.get("screen_height", 1080))
        net_yaw = 0
        net_pitch = 0

        # Clear stuck menus first — a menu left open puts the mouse in
        # menu-mode (camera won't turn), hiding the prompt and blocking
        # any sweep. This must happen before ANY camera movement.
        closed = close_open_menus(v)
        if closed:
            logger.info("Cleared stuck menu(s) before checking: %s", ", ".join(closed))

        inp.focus_game()
        sens = _camera_responds(v)
        if sens is None:
            logger.warning("Camera not responding — cannot navigate to doggo.")
            return result

        # ── Phase 1: LOCKED (saved position known) ──────────────────────
        if saved_pos is not None:
            # Reset pitch to home, then apply saved offsets.
            _reset_pitch_to_home(v, sens)
            saved_yaw = saved_pos["yaw"]
            saved_pitch = saved_pos["pitch"]
            if saved_yaw or saved_pitch:
                inp.move_mouse_relative(saved_yaw, saved_pitch)
                net_yaw = saved_yaw
                net_pitch = saved_pitch
                time.sleep(0.25)
            gp = v.find_in_region("gift_prompt", region)

            if not gp.found:
                # Micro-sweep absorbs minor doggo wandering.
                gp, micro_yaw = _micro_sweep_for_prompt(v, region, sens)
                net_yaw += micro_yaw

            if gp.found:
                logger.info(
                    "[%s] found at saved position (yaw=%d, pitch=%d, conf=%.2f).",
                    name,
                    net_yaw,
                    net_pitch,
                    gp.confidence,
                )
        else:
            gp = v.find_in_region("gift_prompt", region)

        # ── Phase 2: DISCOVERY (no saved position, or locked missed) ────
        if not gp.found:
            logger.info("[%s] not at saved position — entering discovery sweep.", name)
            gp, disc_yaw, disc_pitch = _face_doggo_and_recheck(v, sens)
            # _face_doggo_and_recheck resets pitch to home internally, so
            # our net offsets are now purely what the sweep returned.
            net_yaw = disc_yaw
            net_pitch = disc_pitch

        if not gp.found:
            max_misses = int(cfg.get("taming.max_consecutive_misses", 3))
            if _record_miss_or_reset(name, max_misses):
                logger.warning(
                    "[%s] missed %d cycles in a row — wiping saved position to force re-discovery next cycle.",
                    name,
                    max_misses,
                )
            logger.info(
                "[%s] no gift prompt visible after focus+sweep (conf=%.2f) — "
                "likely lost input focus or player not at the pen.",
                name,
                gp.confidence,
            )
            return result
        result["prompt_found"] = True

        logger.info(
            "[%s] gift prompt at (%d,%d) conf=%.2f — pressing E.",
            name,
            gp.x,
            gp.y,
            gp.confidence,
        )
        # Pressing E only registers when the UE5 viewport holds mouse
        # capture, which a single recapture click restores intermittently,
        # so retry recapture+E until the loot window is confirmed open.
        confirm = _press_until_window_open(v, "doggo_loot_window")
        if not confirm.found:
            logger.warning(
                "[%s] Doggo loot window did not open after %d recapture+E attempts (conf=%.2f). Skipping this cycle.",
                name,
                _OPEN_WINDOW_ATTEMPTS,
                confirm.confidence,
            )
            return result

        # The window title bar shows the doggo's REAL name — the only way
        # to know which doggo we actually opened (no in-world nameplate
        # before interacting).
        ocr_name = _read_loot_window_doggo_name(v)
        matched_name = _any_doggo_name_matches(ocr_name, expected_names)
        if ocr_name and not matched_name:
            # Wrong doggo. Hunt for one of them.
            logger.info("[%s] found '%s' instead — searching.", name, ocr_name)
            press_until_closed(v, "doggo_loot_window")
            search_confirm, ocr_name, search_yaw, search_pitch = _search_for_named_doggo(
                v, region, expected_names, sens
            )
            net_yaw += search_yaw
            net_pitch += search_pitch
            matched_name = _any_doggo_name_matches(ocr_name, expected_names)
            if search_confirm is None or not matched_name:
                logger.warning(
                    "[%s] could not be located after searching (last seen: %s) — skipping this cycle.",
                    name,
                    ocr_name or "nothing",
                )
                return result
            confirm = search_confirm

        # Save/update this doggo's position for the locked fast-path.
        # Works for ALL doggos now (no turn_dx gate).
        if matched_name:
            _save_doggo_position(matched_name, net_yaw, net_pitch)
            _clear_miss_count(matched_name)
            old_pos = saved_pos or {}
            if net_yaw != old_pos.get("yaw", 0) or net_pitch != old_pos.get("pitch", 0):
                logger.info(
                    "[%s] position updated: yaw %d→%d, pitch %d→%d.",
                    matched_name,
                    old_pos.get("yaw", 0),
                    net_yaw,
                    old_pos.get("pitch", 0),
                    net_pitch,
                )

        if ocr_name and not matched_name:
            logger.warning(
                "[%s] loot window title reads '%s' — attributing this check to the OCR name.",
                name,
                ocr_name,
            )
        if ocr_name:
            result["doggo"] = ocr_name

        # Window confirmed open. Coordinates come from config.toml [taming]
        # doggo_loot_slot_x/_y (calibrated for this display); fall back to an
        # offset from the template match centre if not configured.
        slot_x = int(cfg.get("taming.doggo_loot_slot_x", confirm.x))
        slot_y = int(cfg.get("taming.doggo_loot_slot_y", confirm.y + 80))
        hw = int(cfg.get("taming.loot_slot_patch_half_w", 50))
        hh = int(cfg.get("taming.loot_slot_patch_half_h", 55))
        threshold = float(cfg.get("taming.loot_slot_diff_threshold", 12.0))

        # Fast path: if the slot patch matches this doggo's (fresh)
        # empty-slot reference, there is nothing to collect — close and
        # skip the cursor walk (~8s saved on the vast majority of checks).
        # The pre-walk patch is grabbed unconditionally: it doubles as the
        # refresh source when the full path confirms empty below.
        prewalk_patch = v.grab_region(slot_x - hw, slot_y - hh, 2 * hw, 2 * hh)
        # Use stable canonical name for empty reference file keying to avoid caching under noisy OCR spellings
        ref_key_name = matched_name if matched_name else name
        ref = _empty_slot_reference(ref_key_name)
        if ref is not None and ref.shape == prewalk_patch.shape:
            empty_diff = float(np.mean(np.abs(prewalk_patch.astype(np.float32) - ref.astype(np.float32))))
            if empty_diff < threshold:
                window_closed = press_until_closed(v, "doggo_loot_window")
                logger.info(
                    "[%s] slot empty (ref diff=%.1f) — skipped collection walk%s.",
                    result["doggo"],
                    empty_diff,
                    "" if window_closed else " (window may still be open)",
                )
                result["slot_diff"] = round(empty_diff, 2)
                return result

        # ONE cursor trip: park on the slot, read the tooltip while hovering,
        # then shift-click in place (shift_click would re-home and re-walk).
        inp.move_cursor_to(slot_x, slot_y)
        time.sleep(float(cfg.get("taming.tooltip_hover_seconds", 0.6)))
        item_name, _tooltip_crop = _read_item_tooltip(v, slot_x, slot_y)

        # Detect an ACTUAL transfer, not just a successful interaction: most
        # interactions open an empty window (the Doggo only fills its one
        # slot ~0.2%/s), and shift-clicking an empty slot is a documented
        # no-op — so compare a patch centred on the slot before/after the
        # click. This is self-calibrating (works for any item icon) rather
        # than needing an absolute brightness baseline: no-op diff measured
        # live at ~2, a real transfer at ~103.
        before = v.grab_region(slot_x - hw, slot_y - hh, 2 * hw, 2 * hh)
        inp.shift_click_here()
        time.sleep(0.3)
        after = v.grab_region(slot_x - hw, slot_y - hh, 2 * hw, 2 * hh).astype(np.float32)
        diff = float(np.mean(np.abs(before.astype(np.float32) - after)))
        transferred = diff > threshold

        window_closed = press_until_closed(v, "doggo_loot_window")
        logger.info(
            "[%s] loot window %s (slot diff=%.1f, transferred=%s, item=%s).",
            name,
            "closed" if window_closed else "may still be open",
            diff,
            transferred,
            item_name,
        )
        if transferred:
            # Archive the slot icon crop: OCR ground truth for later labeling
            # (and the fallback when the tooltip read fails).
            crops = Path("captures") / "gifts"
            crops.mkdir(parents=True, exist_ok=True)
            crop_path = crops / f"{result['checked_at'].replace(':', '-')}_{name}.png"
            cv2.imwrite(str(crop_path), before)
            result.update(collected=True, item=item_name, slot_diff=round(diff, 2), crop_path=str(crop_path))
        else:
            result["slot_diff"] = round(diff, 2)
            if item_name is None and diff < 3.0:
                # Full path just CONFIRMED the slot is empty (no tooltip
                # band after retries, click was a no-op): refresh this
                # doggo's empty-slot reference so the next checks take the
                # fast path against the current backdrop.
                _refresh_empty_slot_reference(ref_key_name, prewalk_patch)
        return result


@activity.defn
def check_inventory_full() -> bool:
    """
    Opens the player inventory (Tab), scans every slot's centre pixel
    for occupancy, optionally clicks the sort/merge button if all slots
    look occupied, then re-scans and closes the inventory.

    An inventory slot is considered EMPTY when the average brightness of
    a small patch around its centre is below `inventory.empty_slot_brightness`
    (default 35 out of 255 — Satisfactory's empty slots are near-black).

    Sort-button coordinates are read from config.toml
    [inventory_sort_button] x / y.  If those keys are absent the sort
    step is skipped and we rely on the first scan only.
    """
    v = get_vision()
    grid = cfg.get("inventory_grid", {})
    origin_x = int(grid.get("origin_x", 100))
    origin_y = int(grid.get("origin_y", 100))
    slot_w = int(grid.get("slot_w", 90))
    slot_h = int(grid.get("slot_h", 90))
    columns = int(grid.get("columns", 10))
    rows = int(grid.get("rows", 4))
    threshold = int(cfg.get("inventory.empty_slot_brightness", 35))
    patch = 20  # half-width of the pixel patch; larger = more robust vs. item badges
    low_guard = 50  # below this is panel chrome (border/bg), not an empty slot

    def _count_empty(frame: np.ndarray) -> int:
        empty = 0
        h_max, w_max = frame.shape[:2]
        for row in range(rows):
            for col in range(columns):
                cx = origin_x + col * slot_w + slot_w // 2
                cy = origin_y + row * slot_h + slot_h // 2
                # Sample a larger patch and take median brightness (robust vs. badges)
                y0, y1 = max(0, cy - patch), min(h_max, cy + patch)
                x0, x1 = max(0, cx - patch), min(w_max, cx + patch)
                region = frame[y0:y1, x0:x1]
                if region.size == 0:
                    continue
                brightness = float(np.median(region))  # median avoids badge outliers
                # low_guard: panel borders read <50 — ignore them (not a slot at all)
                if low_guard <= brightness < threshold:
                    empty += 1
        return empty

    # Tab is swallowed unless the viewport holds mouse capture; retry
    # recapture+Tab until the inventory panel is confirmed open, otherwise
    # we'd scan the game world and mis-report "full".
    opened = _press_until_window_open(v, "inventory_open", key_action=inp.open_inventory)
    if not opened.found:
        logger.warning(
            "Inventory did not open after %d recapture+Tab attempts "
            "(conf=%.2f). Reporting not-full to avoid a false craft.",
            _OPEN_WINDOW_ATTEMPTS,
            opened.confidence,
        )
        return False
    time.sleep(0.3)  # let the panel finish rendering before sampling

    frame = v.capture()
    empty_count = _count_empty(frame)
    logger.debug("Inventory scan: %d empty slot(s) found.", empty_count)

    if empty_count > 0:
        press_until_closed(v, "inventory_open")
        logger.debug("Inventory has free space (%d empty). Not full.", empty_count)
        return False

    # All slots appear occupied — click the sort/merge button to consolidate
    # stacks (this can free slots by merging partial stacks of the same item).
    sort_x = cfg.get("inventory_sort_button.x", 0)
    sort_y = cfg.get("inventory_sort_button.y", 0)
    if sort_x and sort_y:
        logger.info("All slots occupied — clicking sort button at (%d,%d).", sort_x, sort_y)
        inp.click(int(sort_x), int(sort_y))
        time.sleep(0.5)
        frame = v.capture()
        empty_count = _count_empty(frame)
        logger.debug("Post-sort scan: %d empty slot(s).", empty_count)
    else:
        logger.debug("inventory_sort_button not configured in config.toml — skipping sort step.")

    press_until_closed(v, "inventory_open")
    is_full = empty_count == 0
    logger.info("Inventory full: %s (empty slots after scan: %d).", is_full, empty_count)
    return is_full


@activity.defn
def open_storage_and_deposit_loot() -> int:
    """
    Opens a storage container (needs the interaction prompt in range) and
    sweeps the player's inventory grid with a shift-click on every slot to
    transfer everything at once. Shift-clicking an empty slot does
    nothing, so it's safe to sweep the whole grid without detecting items
    one by one.

    Best-effort: confirms the storage opened, but doesn't verify the
    items were actually transferred. Calibrate [inventory_grid] in
    config.toml with the real coordinates of your inventory layout/resolution.
    """
    with screenshot_on_error("open_storage_and_deposit_loot"):
        v = get_vision()
        prompt = v.find("storage_prompt")
        if not prompt.found:
            raise VisionError("storage_prompt", prompt.confidence, cfg.get("vision.thresholds.storage_prompt", 0.82))

        inp.interact()
        opened = v.wait_for("storage_open", timeout=3.0)
        if not opened.found:
            raise MenuError("Storage window did not open after interacting")

        grid = cfg.get("inventory_grid", {})
        origin_x = grid.get("origin_x", 100)
        origin_y = grid.get("origin_y", 100)
        slot_w = grid.get("slot_w", 90)
        slot_h = grid.get("slot_h", 90)
        columns = grid.get("columns", 10)
        rows = grid.get("rows", 4)

        slots_clicked = 0
        for row in range(rows):
            activity.heartbeat(f"row {row + 1}/{rows} of the inventory")
            for col in range(columns):
                inp.shift_click(origin_x + col * slot_w, origin_y + row * slot_h)
                slots_clicked += 1

        time.sleep(0.3)
        inp.close_menu()
        logger.info("Storage: %d slot(s) swept with shift-click.", slots_clicked)
        return slots_clicked


@activity.defn
def feed_wild_doggo() -> bool:
    """
    Attempts to tame a wild Lizard Doggo: opens the inventory, drags a
    Paleberry to a fixed screen point (drops it in the world, near the
    player) and closes the inventory.

    The success cue (Doggo eats, jumps, and "squeaks") is a weak visual
    signal and isn't verified here — best-effort. Doggos compete for the
    same berry, which is why the workflow calls this activity multiple
    times.
    """
    with screenshot_on_error("feed_wild_doggo"):
        v = get_vision()
        wild = v.find("wild_doggo_prompt")
        if not wild.found:
            logger.debug("No wild Doggo in sight (conf=%.2f)", wild.confidence)
            return False

        inp.open_inventory()
        berry = v.wait_for("paleberry_icon", timeout=2.0)
        if not berry.found:
            inp.close_menu()
            raise VisionError("paleberry_icon", berry.confidence, cfg.get("vision.thresholds.paleberry_icon", 0.85))

        taming = cfg.get("taming", {})
        drop_x = taming.get("drop_point_x", 1280)
        drop_y = taming.get("drop_point_y", 720)
        inp.drag(berry.x, berry.y, drop_x, drop_y)
        time.sleep(0.3)
        inp.close_menu()

        logger.info("Paleberry offered to the wild Doggo (conf=%.2f).", wild.confidence)
        return True


@activity.defn
def download_coal_from_depot(stacks: int = 5) -> int:
    """
    Open player inventory, search for 'coal' in the Dimensional Depot panel,
    and download the specified number of stacks to the player's inventory.
    """
    with screenshot_on_error("download_coal_from_depot"):
        inp.open_inventory()
        time.sleep(0.5)

        # Click search box
        inp.click(700, 242)
        time.sleep(0.1)

        # Clear search box
        for _ in range(20):
            inp.press("backspace")
            time.sleep(0.01)

        # Type "coal"
        for char in "coal":
            inp.press(char)
            time.sleep(0.05)
        time.sleep(0.3)

        # Shift-click the first Depot item (Coal)
        for _ in range(stacks):
            inp.shift_click(522, 320)
            time.sleep(0.15)

        time.sleep(0.2)
        inp.close_menu()
        logger.info("Downloaded %d stacks of Coal from Dimensional Depot.", stacks)
        return stacks


@activity.defn
def deposit_coal_to_storage() -> int:
    """
    Open the storage container in front of the player, locate all Coal stacks
    in the player's inventory grid using template matching, shift-click each
    to deposit them, and close the storage container.
    """
    with screenshot_on_error("deposit_coal_to_storage"):
        v = get_vision()

        # Open storage container
        inp.interact()
        time.sleep(1.0)

        # Grab screen to find matches
        frame = v.capture()

        # Find all Coal slots in the player inventory region
        x, y, w, h = 1450, 200, 580, 500
        sub = frame[y : y + h, x : x + w]

        template = v._load_template("coal_icon")
        th, tw = template.shape[:2]

        res = cv2.matchTemplate(sub, template, cv2.TM_CCOEFF_NORMED)
        threshold = float(cfg.get("vision.thresholds.coal_icon", 0.82))
        loc = np.where(res >= threshold)

        matches: list[tuple[int, int]] = []
        for pt in zip(*loc[::-1], strict=False):
            cx = x + pt[0] + tw // 2
            cy = y + pt[1] + th // 2

            too_close = False
            for mx, my in matches:
                if abs(mx - cx) < 30 and abs(my - cy) < 30:
                    too_close = True
                    break
            if not too_close:
                matches.append((cx, cy))

        # Shift-click all found Coal slots
        deposited = 0
        for cx, cy in matches:
            inp.shift_click(cx, cy)
            deposited += 1
            time.sleep(0.15)

        time.sleep(0.3)
        inp.close_menu()
        logger.info("Deposited %d Coal stacks into storage.", deposited)
        return deposited
