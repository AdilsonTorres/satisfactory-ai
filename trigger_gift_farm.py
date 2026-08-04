import argparse
import asyncio
from typing import Any

from temporalio.client import Client

from utils import config as cfg
from workflows.gift_farm import GiftFarmWorkflow


async def main() -> Any:
    parser = argparse.ArgumentParser(description="Starts the GiftFarmWorkflow (non-blocking).")
    parser.add_argument("--id", default="gift-farm-run", help="Workflow id.")
    parser.add_argument("--ammo-per-craft", type=int, default=50, help="Rifle Ammo per craft cycle.")
    parser.add_argument("--screenshot-every-cycles", type=int, default=10, help="Screenshot every N cycles.")
    parser.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="Seconds to sleep between cycles [60.0]. Each doggo's gift roll "
        "averaged ~15min live, so aggressive polling is mostly menu/camera "
        "churn — use the per-doggo history in stats/gift_history.db to tune.",
    )
    args = parser.parse_args()

    # Roster comes from config.toml [[taming.doggos]] — names key the
    # per-doggo gift history; turn_dx chains doggo-to-doggo camera turns.
    doggos = cfg.get("taming.doggos") or [{"name": "doggo", "turn_dx": 0}]

    client = await Client.connect(cfg.get("temporal.address", "localhost:7233"))
    handle = await client.start_workflow(
        GiftFarmWorkflow.run,
        args=[doggos, args.ammo_per_craft, args.screenshot_every_cycles, args.interval],
        id=args.id,
        task_queue=cfg.get("temporal.task_queue", "satisfactory-bot"),
    )
    print(f"Started GiftFarmWorkflow id={handle.id} run_id={handle.result_run_id}")
    print(f"Roster: {', '.join(d['name'] for d in doggos)}")
    print("Runs continuously (AFK loop) until a 'stop' signal, e.g.:")
    print(f"  await (await Client.connect('localhost:7233')).get_workflow_handle('{args.id}').query('get_stats')")
    print(f"  await (await Client.connect('localhost:7233')).get_workflow_handle('{args.id}').signal('stop')")


if __name__ == "__main__":
    asyncio.run(main())
