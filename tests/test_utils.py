import json
import logging

from utils import exceptions, logger, stats


def test_exceptions():
    # Test inheritance
    assert issubclass(exceptions.VisionError, exceptions.SatisfactoryBotError)
    assert issubclass(exceptions.NavigationError, exceptions.SatisfactoryBotError)
    assert issubclass(exceptions.MenuError, exceptions.SatisfactoryBotError)
    assert issubclass(exceptions.CombatError, exceptions.SatisfactoryBotError)
    assert issubclass(exceptions.RespawnError, exceptions.SatisfactoryBotError)

    # Test VisionError message formatting
    err = exceptions.VisionError("gift_prompt", 0.5432, 0.8)
    assert "gift_prompt" in str(err)
    assert "0.543" in str(err)
    assert "0.800" in str(err)
    assert err.template == "gift_prompt"
    assert err.confidence == 0.5432
    assert err.threshold == 0.8


def test_stats_save(tmp_path, monkeypatch):
    # Mock STATS_DIR with pytest's tmp_path
    monkeypatch.setattr(stats, "STATS_DIR", tmp_path)

    workflow_type = "test_run"
    data = {"somersloops_collected": 12, "mercer_spheres_collected": 7}

    path = stats.save(workflow_type, data)

    # Verify return path
    assert path.parent == tmp_path
    assert path.exists()

    # Verify JSON content
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    assert payload["workflow_type"] == workflow_type
    assert "saved_at" in payload
    assert payload["somersloops_collected"] == 12
    assert payload["mercer_spheres_collected"] == 7


def test_logger_setup(tmp_path, monkeypatch):
    # Mock LOGS_DIR with pytest's tmp_path
    monkeypatch.setattr(logger, "LOGS_DIR", tmp_path)

    # Initialize logger
    logger.setup("DEBUG")

    # Get root logger and check handlers
    root_logger = logging.getLogger()
    assert len(root_logger.handlers) >= 2

    # Log some test messages
    test_logger = logging.getLogger("test_bot")
    test_logger.debug("Debug test message")
    test_logger.info("Info test message")

    # Verify logs were written to bot.log
    log_file = tmp_path / "bot.log"
    assert log_file.exists()

    content = log_file.read_text(encoding="utf-8")
    assert "Debug test message" in content
    assert "Info test message" in content
    assert "DEBUG" in content
    assert "INFO" in content
