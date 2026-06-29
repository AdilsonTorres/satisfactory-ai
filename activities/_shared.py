"""
activities/_shared.py

Shared helpers used by multiple activity modules.
"""

import logging
from contextlib import contextmanager

from utils.screenshot import save_debug_screenshot
from utils.vision import Vision

logger = logging.getLogger(__name__)

_vision: Vision | None = None


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
