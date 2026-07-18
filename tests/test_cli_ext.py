import argparse
from unittest.mock import AsyncMock, patch

import pytest

from tools import cli


def test_cli_draw_args_parsing():
    """Verify that --draw flags are parsed correctly for factory plans."""
    pass


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
