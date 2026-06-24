"""
utils/config.py
Loads config.toml and provides typed access by key path.
"""
import tomllib
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).parent.parent / "config.toml"
_cache: dict | None = None


def load() -> dict:
    global _cache
    if _cache is None:
        if not _CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"config.toml not found at {_CONFIG_PATH}.\n"
                "The file must exist at the project root."
            )
        with open(_CONFIG_PATH, "rb") as f:
            _cache = tomllib.load(f)
    return _cache


def get(key_path: str, default: Any = None) -> Any:
    """Returns a value by dotted path. Ex: get('vision.default_threshold')"""
    try:
        cfg = load()
    except FileNotFoundError:
        return default

    val: Any = cfg
    for k in key_path.split("."):
        if not isinstance(val, dict) or k not in val:
            return default
        val = val[k]
    return val


def reload() -> None:
    """Invalidates the cache — useful in tests."""
    global _cache
    _cache = None
