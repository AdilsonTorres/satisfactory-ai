"""
schedule_gift_farm.py

Auto start/stop windows for GiftFarmWorkflow, via pairs of Temporal
Schedules. Multiple NAMED windows can coexist (e.g. a "daily" 08:00-23:00
window and a "night" 23:10-07:50 window) — each is created/paused/deleted
independently by name, while status/pause/unpause/delete with no --name
apply to every gift-farm-* window found.

Temporal Schedules can only START workflow executions — never signal one
directly. The "stop" side works around that by starting a tiny one-shot
workflow, SignalWorkflowAction, that signals the farm's 'stop' and
completes (see workflows/control.py). All windows target the SAME fixed
workflow id (gift-farm-run), relying on Temporal's default ID-reuse policy
(a new run is allowed once the previous one has closed) — exactly like the
"daily-report" example in Temporal's own docs. Overlapping windows are
harmless: a start while already running is SKIPped, and a stop on an
already-stopped workflow is just a no-op signal-send failure.

Usage:
    uv run python schedule_gift_farm.py create --name night --start 23:10 --stop 07:50 [--timezone ...]
    uv run python schedule_gift_farm.py status
    uv run python schedule_gift_farm.py pause  [--name night]
    uv run python schedule_gift_farm.py unpause [--name night]
    uv run python schedule_gift_farm.py delete [--name night]

For one-off manual control (start/stop/pause/resume any time, schedule or
not), see gift_farm_ctl.py — this script only manages the CRON, not the
workflow's live signals.
"""

import argparse
import asyncio
import contextlib

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleCalendarSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleRange,
    ScheduleSpec,
)

from utils import config as cfg
from workflows.control import SignalWorkflowAction
from workflows.gift_farm import GiftFarmWorkflow

WORKFLOW_ID = "gift-farm-run"
SCHEDULE_PREFIX = "gift-farm-"


def _schedule_ids(name: str) -> tuple[str, str, str]:
    """(start_schedule_id, stop_schedule_id, stop_action_workflow_id) for a named window."""
    return (
        f"{SCHEDULE_PREFIX}{name}-start",
        f"{SCHEDULE_PREFIX}{name}-stop",
        f"{SCHEDULE_PREFIX}{name}-stop-signal",
    )


def _hhmm_to_calendar(hhmm: str, comment: str) -> ScheduleCalendarSpec:
    hour, minute = (int(p) for p in hhmm.split(":"))
    return ScheduleCalendarSpec(hour=[ScheduleRange(hour)], minute=[ScheduleRange(minute)], comment=comment)


async def _client() -> Client:
    return await Client.connect(cfg.get("temporal.address", "localhost:7233"))


async def _discover_schedule_ids(client: Client, name: str | None) -> list[str]:
    """All gift-farm-*-start/-stop schedule ids, or just the named window's if given."""
    if name is not None:
        start_id, stop_id, _ = _schedule_ids(name)
        return [start_id, stop_id]
    ids = []
    async for s in await client.list_schedules():
        if s.id.startswith(SCHEDULE_PREFIX) and (s.id.endswith("-start") or s.id.endswith("-stop")):
            ids.append(s.id)
    return sorted(ids)


async def create(args: argparse.Namespace) -> None:
    client = await _client()
    task_queue = cfg.get("temporal.task_queue", "satisfactory-bot")
    tz = args.timezone or cfg.get("taming.schedule.timezone")
    doggos = cfg.get("taming.doggos") or [{"name": "doggo", "turn_dx": 0}]
    start_id, stop_id, stop_action_workflow_id = _schedule_ids(args.name)

    # Replace this window's own schedules cleanly rather than erroring on
    # re-create; other named windows are left untouched.
    for schedule_id in (start_id, stop_id):
        with contextlib.suppress(Exception):
            await client.get_schedule_handle(schedule_id).delete()

    await client.create_schedule(
        start_id,
        Schedule(
            action=ScheduleActionStartWorkflow(
                GiftFarmWorkflow.run,
                args=[doggos, args.ammo_per_craft, args.screenshot_every_cycles, args.interval],
                id=WORKFLOW_ID,
                task_queue=task_queue,
            ),
            spec=ScheduleSpec(
                calendars=[_hhmm_to_calendar(args.start, f"gift farm '{args.name}' start")], time_zone_name=tz
            ),
            # SKIP: if the farm is already running (started by hand earlier,
            # or another window's start/stop hasn't landed yet), don't pile
            # on another start attempt — just wait for the next tick.
            policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
        ),
    )
    await client.create_schedule(
        stop_id,
        Schedule(
            action=ScheduleActionStartWorkflow(
                SignalWorkflowAction.run,
                args=[WORKFLOW_ID, "stop"],
                id=stop_action_workflow_id,
                task_queue=task_queue,
            ),
            spec=ScheduleSpec(
                calendars=[_hhmm_to_calendar(args.stop, f"gift farm '{args.name}' stop")], time_zone_name=tz
            ),
            policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
        ),
    )
    print(f"Window '{args.name}' created: start {args.start}, stop {args.stop} ({tz or 'UTC'}).")
    print("Manual control any time: uv run python gift_farm_ctl.py start|stop|pause|resume|status")
    print(f"Disable this window:     uv run python schedule_gift_farm.py pause|delete --name {args.name}")


async def pause(args: argparse.Namespace) -> None:
    client = await _client()
    ids = await _discover_schedule_ids(client, args.name)
    for sid in ids:
        await client.get_schedule_handle(sid).pause(note="paused via schedule_gift_farm.py")
    print(f"Paused: {', '.join(ids) if ids else '(none found)'} (an already-running workflow is untouched).")


async def unpause(args: argparse.Namespace) -> None:
    client = await _client()
    ids = await _discover_schedule_ids(client, args.name)
    for sid in ids:
        await client.get_schedule_handle(sid).unpause()
    print(f"Unpaused: {', '.join(ids) if ids else '(none found)'}.")


async def delete(args: argparse.Namespace) -> None:
    client = await _client()
    ids = await _discover_schedule_ids(client, args.name)
    for sid in ids:
        try:
            await client.get_schedule_handle(sid).delete()
            print(f"  {sid}: deleted")
        except Exception as exc:
            print(f"  {sid}: {exc}")
    print("An already-running workflow, if any, keeps running.")


async def status(args: argparse.Namespace) -> None:
    client = await _client()
    ids = await _discover_schedule_ids(client, args.name)
    if not ids:
        print("No gift-farm schedules found (run 'create' first).")
        return
    for sid in ids:
        try:
            desc = await client.get_schedule_handle(sid).describe()
            state = "paused" if desc.schedule.state.paused else "active"
            next_runs = desc.info.next_action_times[:1]
            when = next_runs[0].isoformat() if next_runs else "n/a"
            print(f"{sid}: {state}, next run: {when}")
        except Exception:
            print(f"{sid}: not found (run 'create' first)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto start/stop schedule windows for GiftFarmWorkflow.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Create/replace a named start+stop window")
    p_create.add_argument("--name", default="daily", help="Window name, e.g. 'daily' or 'night' [daily]")
    p_create.add_argument("--start", default=cfg.get("taming.schedule.start_time", "08:00"), help="Window start HH:MM")
    p_create.add_argument("--stop", default=cfg.get("taming.schedule.stop_time", "23:00"), help="Window stop HH:MM")
    p_create.add_argument(
        "--timezone",
        default=None,
        help="IANA tz name (e.g. America/Sao_Paulo); overrides config.toml [taming.schedule].timezone",
    )
    p_create.add_argument("--ammo-per-craft", type=int, default=50)
    p_create.add_argument("--screenshot-every-cycles", type=int, default=10)
    p_create.add_argument("--interval", type=float, default=50.0)
    p_create.set_defaults(func=create)

    for name, fn, help_ in (
        ("pause", pause, "Disable a window (or all, if --name omitted); a running workflow is untouched"),
        ("unpause", unpause, "Re-enable a window (or all, if --name omitted)"),
        ("delete", delete, "Remove a window entirely (or all, if --name omitted)"),
        ("status", status, "Show state and next run times for a window (or all, if --name omitted)"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--name", default=None, help="Window name; omit to act on every gift-farm window")
        p.set_defaults(func=fn)

    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
