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

    parsed_lg_html = parser.parse_args(
        ["plan-late-game", "--item", "Ballistic Warp Drive", "--rate", "5", "--draw-html"]
    )
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

    test_args = [
        "trigger_depot_coal.py",
        "--id",
        "depot-coal-custom",
        "--interval",
        "10",
        "--max-cycles",
        "5",
        "--stacks-per-cycle",
        "2",
    ]
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

    test_args = [
        "trigger_gift_farm.py",
        "--id",
        "gift-farm-custom",
        "--ammo-per-craft",
        "40",
        "--screenshot-every-cycles",
        "5",
        "--interval",
        "120",
    ]
    with patch.object(sys, "argv", test_args):
        await trigger_gift_farm.main()

    mock_client.start_workflow.assert_called_once()
    call_args = mock_client.start_workflow.call_args
    assert call_args[1]["id"] == "gift-farm-custom"
    assert call_args[1]["args"][1:] == [40, 5, 120.0]


def test_map_draw_html_arg_parsing():
    """Verify that --draw-html option is parsed correctly for the map subcommand."""
    parser = cli.create_parser()
    parsed = parser.parse_args(["map", "--draw-html"])
    assert parsed.draw_html is True

    parsed_no_draw = parser.parse_args(["map"])
    assert parsed_no_draw.draw_html is False


def test_dashboard_arg_parsing():
    """Verify that dashboard subcommand is parsed correctly with --port option."""
    parser = cli.create_parser()
    parsed = parser.parse_args(["dashboard", "--port", "9000"])
    assert parsed.command == "dashboard"
    assert parsed.port == 9000


@patch("tools.dashboard.start_server")
def test_run_dashboard_invokes_start_server(mock_start_server):
    """Verify that _run_dashboard invokes tools.dashboard.start_server."""
    args = argparse.Namespace()
    args.port = 8888
    cli._run_dashboard(args)
    mock_start_server.assert_called_once_with(8888)


def test_save_map_html():
    """Verify that _save_map_html correctly writes the map file."""
    map_data = {
        "stats": {
            "player_position": [0, 0, 0],
            "is_currently_powered": True,
            "total_active_nodes": 1,
            "total_wires": 1,
            "reachable_nodes_count": 1,
            "reachable_wires_count": 0,
            "reachable_network_length_meters": 0.0,
        },
        "reachable_nodes": [{"id": "node_1", "type": "Pole_C", "pos": [1000, 1000, 0], "range": 3000.0}],
        "reachable_wires": [],
    }
    pois = {"lizard_doggos": [{"name": "Rex", "pos": [500, 500, 0]}], "drop_pods": [], "enemy_nests": []}

    with patch("webbrowser.open") as mock_open:
        path_str = cli._save_map_html(map_data, pois)
        path = Path(path_str)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Hover Pack Grid Map" in content
        assert "Rex" in content
        mock_open.assert_called_once()
        path.unlink()


def test_dashboard_handler_endpoints():
    """Verify that DashboardHandler internal methods run without error and return expected structures."""
    from tools.dashboard import DashboardHandler

    handler = MagicMock(spec=DashboardHandler)
    handler._get_stats_data = DashboardHandler._get_stats_data
    handler._get_screenshots_list = DashboardHandler._get_screenshots_list

    stats = handler._get_stats_data(handler)
    assert "gift_summary" in stats
    assert "recent_runs" in stats

    screenshots = handler._get_screenshots_list(handler)
    assert isinstance(screenshots, list)


def test_dashboard_watcher_thread():
    """Verify watcher globals are present and initialized."""
    import tools.dashboard as db

    assert hasattr(db, "global_save_version")
    assert hasattr(db, "global_last_modified")
    assert hasattr(db, "global_watcher_active")


def test_update_config_value():
    """Verify that update_config_value correctly updates properties inside config.toml."""
    from tools.dashboard import update_config_value
    temp_config = Path("config.toml")
    backup = None
    if temp_config.exists():
        backup = temp_config.read_text(encoding="utf-8")

    try:
        temp_config.write_text("[vision]\ndefault_threshold = 0.8\n# some comment\n", encoding="utf-8")
        success = update_config_value("vision", "default_threshold", 0.95)
        assert success is True
        content = temp_config.read_text(encoding="utf-8")
        assert "default_threshold = 0.95" in content
        assert "# some comment" in content
    finally:
        if backup is not None:
            temp_config.write_text(backup, encoding="utf-8")
        else:
            temp_config.unlink()


def test_dist_3d_calculation():
    """Verify 3D distance calculations in map_power."""
    from tools.map_power import dist_3d
    assert dist_3d([0, 0, 0], [300, 400, 0]) == 500.0


def test_async_workflow_and_schedule_triggers():
    """Verify that _trigger_workflow_async and _run_schedule_action_async map parameters correctly."""
    from tools.dashboard import DashboardHandler

    handler = MagicMock(spec=DashboardHandler)
    handler._trigger_workflow_async = DashboardHandler._trigger_workflow_async
    handler._run_schedule_action_async = DashboardHandler._run_schedule_action_async

    with (
        patch("temporalio.client.Client.connect") as mock_connect,
        patch("schedule_gift_farm.pause") as mock_pause,
    ):
        handler._trigger_workflow_async(handler, "calibration", {"target": "hud"})
        mock_connect.assert_called_once()

        handler._run_schedule_action_async(handler, "pause", "daily")
        mock_pause.assert_called_once()

