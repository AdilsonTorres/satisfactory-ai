"""
utils/logger.py
Logging to console + rotating file at logs/bot.log.
"""
import logging
import logging.handlers
from pathlib import Path

LOGS_DIR = Path("logs")
_FMT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"


def setup(level: str = "INFO") -> None:
    """Initializes logging. Call once at worker startup."""
    LOGS_DIR.mkdir(exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / "bot.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB per file
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(_FMT))

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(_FMT))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[console_handler, file_handler],
        force=True,
    )
