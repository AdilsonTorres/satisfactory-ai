"""
workers/orchestrator.py

ORCHESTRATOR worker — runs inside Docker (see docker-compose.yml `worker`
service) and keeps workflows progressing 24/7 regardless of what happens
to the host desktop session.

Two Temporal workers in one process:
  * workflow worker  — ALL workflows on the main task queue, NO activities
    (so it never polls activity tasks there; those go to the host game
    worker, and simply wait in the queue while that worker is offline).
  * persist worker   — persistence activities (stats JSON, SQLite gift
    history) on the persist queue; ./stats is a bind mount, so the data
    lands on the host filesystem.

TEMPORAL_ADDRESS env overrides config.toml (in-compose it's temporal:7233).
"""

import asyncio
import logging
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Worker

from activities import PERSIST_ACTIVITIES
from utils import config as cfg
from utils import logger as log
from workflows import ALL_WORKFLOWS

_logger = logging.getLogger(__name__)


async def main() -> None:
    log.setup(cfg.get("logging.level", "INFO"))

    address   = os.environ.get("TEMPORAL_ADDRESS") or cfg.get("temporal.address", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE") or cfg.get("temporal.namespace", "default")
    wf_queue  = cfg.get("temporal.task_queue", "satisfactory-bot")
    persist_queue = cfg.get("temporal.persist_task_queue", "satisfactory-persist")

    # Retry connecting: in compose this container often starts before the
    # temporal service finishes auto-setup.
    while True:
        try:
            _logger.info("Connecting to Temporal at %s ...", address)
            client = await Client.connect(address, namespace=namespace)
            break
        except RuntimeError as exc:
            _logger.warning("Temporal not reachable yet (%s) — retrying in 5s.", exc)
            await asyncio.sleep(5)
    _logger.info("Connected. ns=%s | wf_queue='%s' | persist_queue='%s'", namespace, wf_queue, persist_queue)

    hostname = socket.gethostname()
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="persist") as persist_executor:
        workflow_worker = Worker(
            client,
            task_queue=wf_queue,
            workflows=ALL_WORKFLOWS,
            identity=f"satisfactory-orchestrator@{hostname}",
        )
        persist_worker = Worker(
            client,
            task_queue=persist_queue,
            activities=PERSIST_ACTIVITIES,
            activity_executor=persist_executor,
            identity=f"satisfactory-persist@{hostname}",
            graceful_shutdown_timeout=timedelta(seconds=5),
        )
        _logger.info("Orchestrator worker active.")
        await asyncio.gather(workflow_worker.run(), persist_worker.run())


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
