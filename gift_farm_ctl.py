"""
gift_farm_ctl.py

Convenience control for GiftFarmWorkflow: start / stop / pause / resume /
status, so you don't need to remember raw Temporal signal/query calls.

Usage:
    uv run python gift_farm_ctl.py start [--interval 50] [--ammo-per-craft 50]
    uv run python gift_farm_ctl.py stop
    uv run python gift_farm_ctl.py pause
    uv run python gift_farm_ctl.py resume
    uv run python gift_farm_ctl.py status

For automatic daily start/stop, see schedule_gift_farm.py instead — it
uses these same signals under the hood, on a cron.
"""

import argparse
import asyncio

from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from utils import config as cfg
from workflows.gift_farm import GiftFarmWorkflow

WORKFLOW_ID = "gift-farm-run"


async def _client() -> Client:
    return await Client.connect(cfg.get("temporal.address", "localhost:7233"))


async def start(args: argparse.Namespace) -> None:
    client = await _client()
    doggos = cfg.get("taming.doggos") or [{"name": "doggo", "turn_dx": 0}]
    try:
        handle = await client.start_workflow(
            GiftFarmWorkflow.run,
            args=[doggos, args.ammo_per_craft, args.screenshot_every_cycles, args.interval],
            id=WORKFLOW_ID,
            task_queue=cfg.get("temporal.task_queue", "satisfactory-bot"),
        )
        print(f"Started GiftFarmWorkflow id={handle.id} run_id={handle.result_run_id}")
        print(f"Roster: {', '.join(d['name'] for d in doggos)}")
    except WorkflowAlreadyStartedError:
        print(f"Already running (workflow id '{WORKFLOW_ID}'). Use 'status' to check, 'stop' to end it first.")


async def stop(args: argparse.Namespace) -> None:
    client = await _client()
    try:
        await client.get_workflow_handle(WORKFLOW_ID).signal("stop")
        print("Stop signal sent — it finishes the current step, saves stats, then ends.")
    except Exception as exc:
        print(f"Could not signal stop (is it running?): {exc}")


async def pause(args: argparse.Namespace) -> None:
    client = await _client()
    try:
        await client.get_workflow_handle(WORKFLOW_ID).signal("pause")
        print("Pause signal sent.")
    except Exception as exc:
        print(f"Could not signal pause (is it running?): {exc}")


async def resume(args: argparse.Namespace) -> None:
    client = await _client()
    try:
        await client.get_workflow_handle(WORKFLOW_ID).signal("resume")
        print("Resume signal sent.")
    except Exception as exc:
        print(f"Could not signal resume (is it running?): {exc}")


async def status(args: argparse.Namespace) -> None:
    client = await _client()
    handle = client.get_workflow_handle(WORKFLOW_ID)
    try:
        desc = await handle.describe()
        stats = await handle.query("get_stats")
        status_name = desc.status.name if desc.status else "UNKNOWN"
        print(f"Workflow status: {status_name}")
        print(f"Stats: {stats}")
    except Exception as exc:
        print(f"Not running / not found: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Start/stop/pause/resume/status for GiftFarmWorkflow.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="Start the farm (no-op with a message if already running)")
    p_start.add_argument("--ammo-per-craft", type=int, default=50)
    p_start.add_argument("--screenshot-every-cycles", type=int, default=10)
    p_start.add_argument("--interval", type=float, default=50.0)
    p_start.set_defaults(func=start)

    for name, fn, help_ in (
        ("stop", stop, "Signal a graceful stop (finishes current step, saves stats, ends)"),
        ("pause", pause, "Pause between steps without ending the workflow"),
        ("resume", resume, "Resume a paused workflow"),
        ("status", status, "Show run status and live stats"),
    ):
        p = sub.add_parser(name, help=help_)
        p.set_defaults(func=fn)

    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
