"""
utils/exceptions.py
Bot exception hierarchy.
Descriptive names show up in Temporal's history to make debugging easier.
"""


class SatisfactoryBotError(Exception):
    """Base error — all bot errors inherit from this."""


class VisionError(SatisfactoryBotError):
    """Template not found on screen with enough confidence."""

    def __init__(self, template: str, confidence: float, threshold: float):
        self.template = template
        self.confidence = confidence
        self.threshold = threshold
        super().__init__(
            f"Template '{template}' not found. "
            f"Best conf: {confidence:.3f} < threshold: {threshold:.3f}. "
            f"Run: uv run python debug_run.py --find {template}"
        )


class NavigationError(SatisfactoryBotError):
    """Workshop or destination not found after a movement sequence."""


class MenuError(SatisfactoryBotError):
    """Menu did not open or is not in the expected state."""


class CombatError(SatisfactoryBotError):
    """Unexpected state during combat."""


class RespawnError(SatisfactoryBotError):
    """Respawn button not found on the death screen."""
