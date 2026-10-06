"""CLI scope contracts without a real Temporal server or game dependencies."""

import argparse
import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.mark.parametrize("operation", ["calibration", "exploration", "status"])
@pytest.mark.parametrize("use_environment", [False, True])
def test_cli_uses_worker_address_namespace_and_queue(monkeypatch, operation, use_environment):
    settings = {
        "temporal.address": "configured.invalid:7233",
        "temporal.namespace": "configured-bot",
        "temporal.task_queue": "configured-game-queue",
    }
    config = types.SimpleNamespace(get=lambda key, default=None: settings.get(key, default))
    utils = types.ModuleType("utils")
    utils.config = config
    monkeypatch.setitem(sys.modules, "utils", utils)
    if use_environment:
        monkeypatch.setenv("TEMPORAL_ADDRESS", "override.invalid:7233")
        monkeypatch.setenv("TEMPORAL_NAMESPACE", "override-bot")
    else:
        monkeypatch.delenv("TEMPORAL_ADDRESS", raising=False)
        monkeypatch.delenv("TEMPORAL_NAMESPACE", raising=False)

    async def empty_workflows(_query):
        for item in ():
            yield item

    client = types.SimpleNamespace(execute_workflow=AsyncMock(return_value={}), list_workflows=empty_workflows)
    connect = AsyncMock(return_value=client)
    temporal = types.ModuleType("temporalio")
    temporal_client = types.ModuleType("temporalio.client")
    temporal_client.Client = types.SimpleNamespace(connect=connect)
    monkeypatch.setitem(sys.modules, "temporalio", temporal)
    monkeypatch.setitem(sys.modules, "temporalio.client", temporal_client)
    monkeypatch.setitem(sys.modules, "workflows", types.ModuleType("workflows"))
    for module_name, class_name in (
        ("template_orchestration", "TemplateOrchestrationWorkflow"),
        ("exploration", "ExplorationWorkflow"),
    ):
        workflow_module = types.ModuleType(f"workflows.{module_name}")
        setattr(workflow_module, class_name, types.SimpleNamespace(run=object()))
        monkeypatch.setitem(sys.modules, f"workflows.{module_name}", workflow_module)

    source = Path(__file__).resolve().parents[1] / "tools/cli.py"
    spec = importlib.util.spec_from_file_location("sat_cli_scope_fixture", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if operation == "calibration":
        asyncio.run(module._trigger_calibration(argparse.Namespace(target="hud", resolution="fixture")))
    elif operation == "exploration":
        asyncio.run(
            module._trigger_exploration(
                argparse.Namespace(id="offline-fixture", max_seconds=1, ignore_health=False, no_return=False)
            )
        )
    else:
        asyncio.run(module._run_status())
    address = "override.invalid:7233" if use_environment else "configured.invalid:7233"
    namespace = "override-bot" if use_environment else "configured-bot"
    connect.assert_awaited_once_with(target_host=address, namespace=namespace)
    if operation != "status":
        assert client.execute_workflow.await_args.kwargs["task_queue"] == "configured-game-queue"
