import argparse
import asyncio

from temporalio.client import Client

from utils import config as cfg
from workflows.depot_coal import DepotCoalToStorageWorkflow


async def main():
    parser = argparse.ArgumentParser(description="Starts the DepotCoalToStorageWorkflow (non-blocking).")
    parser.add_argument("--id", default="depot-coal-run", help="Workflow id.")
    parser.add_argument("--interval", type=float, default=15.0, help="Seconds to sleep between cycles.")
    parser.add_argument("--max-cycles", type=int, default=None, help="Stop after N cycles.")
    parser.add_argument(
        "--stacks-per-cycle", type=int, default=5, help="Stacks of Coal to download/transfer each cycle."
    )
    args = parser.parse_args()

    client = await Client.connect(cfg.get("temporal.address", "localhost:7233"))
    handle = await client.start_workflow(
        DepotCoalToStorageWorkflow.run,
        args=[args.interval, args.max_cycles, args.stacks_per_cycle],
        id=args.id,
        task_queue=cfg.get("temporal.task_queue", "satisfactory-bot"),
    )
    print(f"Started DepotCoalToStorageWorkflow id={handle.id} run_id={handle.result_run_id}")
    print(f"Interval: {args.interval}s | Stacks per cycle: {args.stacks_per_cycle} | Max cycles: {args.max_cycles}")
    print("Runs continuously until a 'stop' signal, e.g.:")
    print(f"  await (await Client.connect('localhost:7233')).get_workflow_handle('{args.id}').query('get_stats')")
    print(f"  await (await Client.connect('localhost:7233')).get_workflow_handle('{args.id}').signal('stop')")


if __name__ == "__main__":
    asyncio.run(main())
