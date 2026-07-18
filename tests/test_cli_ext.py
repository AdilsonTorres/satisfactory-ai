import argparse
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import trigger_calibration
import trigger_depot_coal
import trigger_exploration
import trigger_gift_farm
from tools import cli


def test_cli_draw_args_parsing():
    """Verify that --draw and --draw-html flags are parsed correctly for factory plans."""
    parser = cli.create_parser()

    # plan-production
    parsed = parser.parse_args(["plan-production", "--item", "Modular Frame", "--rate", "10", "--draw"])
    assert parsed.draw is True
    assert parsed.draw_html is False

    parsed_html = parser.parse_args(["plan-production", "--item", "Modular Frame", "--rate", "10", "--draw-html"])
    assert parsed_html.draw is False
    assert parsed_html.draw_html is True

    # plan-late-game
    parsed_lg = parser.parse_args(["plan-late-game", "--item", "Ballistic Warp Drive", "--rate", "5", "--draw"])
    assert parsed_lg.draw is True
    assert parsed_lg.draw_html is False

    parsed_lg_html = parser.parse_args(["plan-late-game", "--item", "Ballistic Warp Drive", "--rate", "5", "--draw-html"])
    assert parsed_lg_html.draw is False
    assert parsed_lg_html.draw_html is True


def test_save_flowchart_html():
    """Verify that _save_flowchart_html correctly generates and saves an HTML flowchart."""
    markup = "graph TD\n    A --> B"
    with patch("webbrowser.open") as mock_open:
        path_str = cli._save_flowchart_html(markup, "Test Item")
        path = Path(path_str)
        assert path.exists()
        assert "graph TD" in path.read_text(encoding="utf-8")
        assert "Test Item" in path.read_text(encoding="utf-8")
        mock_open.assert_called_once()
        # Cleanup
        path.unlink()


@pytest.mark.asyncio
@patch("temporalio.client.Client.connect")
async def test_run_status_offline(mock_connect):
    """Test that _run_status behaves correctly if Temporal is unreachable."""
    mock_connect.side_effect = RuntimeError("Connection refused")

    with pytest.raises(SystemExit):
        await cli._run_status()


@pytest.mark.asyncio
@patch("schedule_gift_farm.status", new_callable=AsyncMock)
async def test_run_schedules_list(mock_status):
    """Test that schedules list routes properly to schedule_gift_farm.status."""
    args = argparse.Namespace()
    args.action = "list"
    args.name = None

    await cli._run_schedules(args)

    mock_status.assert_called_once()
    called_arg = mock_status.call_args[0][0]
    assert called_arg.name is None


# ==============================================================================
# Script Triggers Integration Tests
# ==============================================================================
@pytest.mark.asyncio
@patch("temporalio.client.Client.connect")
async def test_trigger_exploration(mock_connect):
    """Test trigger_exploration script execution."""
    mock_client = MagicMock()
    mock_client.execute_workflow = AsyncMock(return_value={"status": "completed"})
    mock_connect.return_value = mock_client

    test_args = ["trigger_exploration.py", "--id", "custom-exploration", "--max-seconds", "300", "--ignore-health"]
    with patch.object(sys, "argv", test_args):
        await trigger_exploration.main()

    mock_client.execute_workflow.assert_called_once()
    call_args = mock_client.execute_workflow.call_args
    assert call_args[1]["id"] == "custom-exploration"
    assert call_args[1]["args"] == [300.0, True]


@pytest.mark.asyncio
@patch("temporalio.client.Client.connect")
async def test_trigger_calibration(mock_connect):
    """Test trigger_calibration script execution."""
    mock_client = MagicMock()
    mock_client.execute_workflow = AsyncMock(return_value={"success": True})
    mock_connect.return_value = mock_client

    test_args = ["trigger_calibration.py", "--target", "workshop", "--resolution", "1920x1080"]
    with patch.object(sys, "argv", test_args):
        await trigger_calibration.main()

    mock_client.execute_workflow.assert_called_once()
    call_args = mock_client.execute_workflow.call_args
    assert call_args[1]["id"] == "calibration-workflow-run"
    assert call_args[1]["args"] == ["workshop", "1920x1080"]


@pytest.mark.asyncio
@patch("temporalio.client.Client.connect")
async def test_trigger_depot_coal(mock_connect):
    """Test trigger_depot_coal script execution."""
    mock_client = MagicMock()
    mock_handle = MagicMock()
    mock_handle.id = "depot-coal-run"
    mock_handle.result_run_id = "run-abc"
    mock_client.start_workflow = AsyncMock(return_value=mock_handle)
    mock_connect.return_value = mock_client

    test_args = ["trigger_depot_coal.py", "--id", "depot-coal-custom", "--interval", "10", "--max-cycles", "5", "--stacks-per-cycle", "2"]
    with patch.object(sys, "argv", test_args):
        await trigger_depot_coal.main()

    mock_client.start_workflow.assert_called_once()
    call_args = mock_client.start_workflow.call_args
    assert call_args[1]["id"] == "depot-coal-custom"
    assert call_args[1]["args"] == [10.0, 5, 2]


@pytest.mark.asyncio
@patch("temporalio.client.Client.connect")
async def test_trigger_gift_farm(mock_connect):
    """Test trigger_gift_farm script execution."""
    mock_client = MagicMock()
    mock_handle = MagicMock()
    mock_handle.id = "gift-farm-run"
    mock_handle.result_run_id = "run-xyz"
    mock_client.start_workflow = AsyncMock(return_value=mock_handle)
    mock_connect.return_value = mock_client

    test_args = ["trigger_gift_farm.py", "--id", "gift-farm-custom", "--ammo-per-craft", "40", "--screenshot-every-cycles", "5", "--interval", "120"]
    with patch.object(sys, "argv", test_args):
        await trigger_gift_farm.main()

    mock_client.start_workflow.assert_called_once()
    call_args = mock_client.start_workflow.call_args
    assert call_args[1]["id"] == "gift-farm-custom"
    assert call_args[1]["args"][1:] == [40, 5, 120.0]
