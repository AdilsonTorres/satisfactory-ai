from typing import Any

import pytest

from utils import config


def test_config_load() -> None:
    # Make sure we can load the config file
    cfg = config.load()
    assert isinstance(cfg, dict)
    assert "temporal" in cfg
    assert "vision" in cfg


def test_config_get_existing() -> None:
    # Test getting standard values
    addr = config.get("temporal.address")
    assert addr == "172.28.125.187:7233"

    tq = config.get("temporal.task_queue")
    assert tq == "satisfactory-bot"


def test_config_get_nested() -> None:
    # Test nested dict lookups
    gift_thr = config.get("vision.thresholds.gift_prompt")
    assert isinstance(gift_thr, float)
    assert gift_thr > 0.0


def test_config_get_default() -> None:
    # Test getting non-existent keys returns the specified default
    assert config.get("nonexistent.key", "default_val") == "default_val"
    assert config.get("temporal.nonexistent", None) is None


def test_config_reload() -> None:
    # Verify reload clears the cache
    config.reload()
    assert config._cache is None
    # Load again to populate
    config.load()
    assert config._cache is not None
    config.reload()
    assert config._cache is None


def test_config_missing_file(monkeypatch: Any, tmp_path: Any) -> None:
    # Set config path to a non-existent file and check load error
    missing_file = tmp_path / "missing_config.toml"
    monkeypatch.setattr(config, "_CONFIG_PATH", missing_file)

    # Reload to ensure it attempts to read the missing file
    config.reload()
    with pytest.raises(FileNotFoundError):
        config.load()

    # config.get should swallow FileNotFoundError and return default
    assert config.get("temporal.address", "fallback") == "fallback"
