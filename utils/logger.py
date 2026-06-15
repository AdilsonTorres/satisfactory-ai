"""
utils/logger.py
Logging para console + arquivo rotativo em logs/bot.log.
"""
import logging
import logging.handlers
from pathlib import Path

LOGS_DIR = Path("logs")
_FMT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"


def setup(level: str = "INFO") -> None:
    """Inicializa logging. Chame uma vez no startup do worker."""
    LOGS_DIR.mkdir(exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / "bot.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB por arquivo
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
