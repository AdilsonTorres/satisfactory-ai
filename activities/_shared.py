"""
activities/_shared.py

Shared helpers used by multiple activity modules.
"""

import logging
import time
from contextlib import contextmanager

from utils import input as inp
from utils.screenshot import save_debug_screenshot
from utils.vision import MatchResult, Vision

logger = logging.getLogger(__name__)

_vision: Vision | None = None

# How many recapture/focus + key attempts before giving up on a menu toggle.
# UE5 drops keyboard input until the viewport regains mouse capture, and a
# single recapture only restores it ~50-65% of the time, so we verify the
# menu state against a template and retry. Detection is crisp (~0.98 vs ~0.45),
# so 5 attempts gives >98% effective reliability.
MENU_TOGGLE_ATTEMPTS = 5


def _finder(v: Vision, template: str, region):
    """A zero-arg callable that looks for `template`, region-cropped if given."""
    if region is not None:
        return lambda: v.find_in_region(template, region)
    return lambda: v.find(template)


def press_until_open(
    v: Vision,
    template: str,
    key_action=inp.interact,
    attempts: int = MENU_TOGGLE_ATTEMPTS,
    settle: float = 0.8,
    region: tuple[int, int, int, int] | None = None,
) -> MatchResult:
    """
    Recapture the game's mouse focus and press `key_action`, retrying until
    `template` is detected (the UI opened) or the attempt budget is exhausted.

    Returns the final MatchResult (check `.found`). Used wherever a keyboard
    press must OPEN a UI: the press is silently swallowed unless the UE5
    viewport holds mouse capture, so verifying + retrying makes it reliable.
    """
    find = _finder(v, template, region)
    result = find()
    n = 0
    while not result.found and n < attempts:
        n += 1
        inp.ensure_game_input_ready()
        key_action()
        time.sleep(settle)
        result = find()
        logger.debug(
            "open %s attempt %d/%d: conf=%.2f found=%s",
            template, n, attempts, result.confidence, result.found,
        )
    return result


def press_until_closed(
    v: Vision,
    template: str,
    attempts: int = MENU_TOGGLE_ATTEMPTS,
    settle: float = 0.5,
    region: tuple[int, int, int, int] | None = None,
) -> bool:
    """
    Press Escape (with focus) until `template` is NO LONGER detected, i.e. the
    menu it identifies is confirmed closed. Returns True when closed.

    Crucially, this presses Escape ONLY while the menu is still visible and
    stops the instant it's gone — so it never over-presses. A blind
    double-Escape is the classic desync bug: if the first Escape closes the
    only open menu, the second one OPENS the pause menu, leaving a menu up.
    """
    find = _finder(v, template, region)
    for n in range(attempts):
        if not find().found:
            return True
        inp.focus_game()
        inp.press("escape", delay_after=settle)
        logger.debug("close %s attempt %d/%d", template, n + 1, attempts)
    closed = not find().found
    if not closed:
        logger.warning("%s still open after %d Escape attempts.", template, attempts)
    return closed


def get_vision() -> Vision:
    global _vision
    if _vision is None:
        _vision = Vision()
    return _vision


@contextmanager
def screenshot_on_error(label: str):
    """Saves a screenshot if the activity raises an exception."""
    try:
        yield
    except Exception as exc:
        path = save_debug_screenshot(f"error_{label}")
        logger.error("[%s] %s: %s | screenshot: %s", label, type(exc).__name__, exc, path)
        raise


def _check_health_inline(v: Vision, frame=None) -> bool:
    """
    Checks for LOW health directly via Vision — no Temporal dispatch.
    Used inside engage_enemy (you can't call another activity from
    inside an activity; using the decorator would just call the local
    function, not a new Temporal execution).

    Reads the actual health bar (lit segments) via read_player_status().
    The old implementation matched 'health_low_indicator' — but that
    template is just the heart icon, which is on the HUD at ANY health
    level, so it reported "low health" at full health (conf ~0.95 every
    frame, confirmed live 2026-06-25). The `frame` arg is kept for call
    compatibility but ignored: the status reader does its own fast,
    region-cropped grab of just the HUD.
    """
    status = v.read_player_status()
    if status["health_low"]:
        logger.warning(
            "Low health: %d/10 segments (frac=%.2f).",
            status["health_segments"],
            status["health_frac"],
        )
    return bool(status["health_low"])
