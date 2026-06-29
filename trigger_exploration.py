import argparse
import asyncio
import json

from temporalio.client import Client

from workflows.exploration import ExplorationWorkflow


async def main():
    parser = argparse.ArgumentParser(description="Triggers the ExplorationWorkflow.")
    parser.add_argument("--id", default="exploration-run", help="Workflow id.")
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Override exploration.max_total_duration_seconds (movement budget).",
    )
    parser.add_argument(
        "--ignore-health", action="store_true", help="Skip the low-health abort (death detection still applies)."
    )
    args = parser.parse_args()

    client = await Client.connect("localhost:7233")
    print(f"Connected. Starting ExplorationWorkflow(id={args.id}, max_seconds={args.max_seconds})...")

    result = await client.execute_workflow(
        ExplorationWorkflow.run,
        args=[args.max_seconds, args.ignore_health],
        id=args.id,
        task_queue="satisfactory-bot",
    )
    print("\n=== Workflow completed ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
