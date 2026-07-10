"""
activities/control.py

Control-plane activities: signal an EXISTING workflow from another workflow.
Temporal Schedules can only START workflow executions, never signal one
directly — this activity is the bridge a Schedule uses to, e.g., stop the
gift farm at closing time (see workflows/control.py, schedule_gift_farm.py).

Pure Temporal-client I/O, no game/UI/DB access, so this runs on the persist
queue in the Dockerized orchestrator — available even if the host game
worker is offline.
"""

import asyncio
import logging
import os

from temporalio import activity
from temporalio.client import Client

from utils import config as cfg

logger = logging.getLogger(__name__)


@activity.defn
def send_workflow_signal(target_workflow_id: str, signal_name: str) -> None:
    """
    Connects a fresh Temporal client and sends `signal_name` to
    `target_workflow_id`. Failure (target already stopped/completed, or
    never started) is logged and swallowed rather than raised — a missing
    target is a normal outcome here (e.g. the farm was already stopped by
    hand before the scheduled stop fired), not something worth retrying.
    """

    async def _send() -> None:
        address = os.environ.get("TEMPORAL_ADDRESS") or cfg.get("temporal.address", "localhost:7233")
        client = await Client.connect(address)
        handle = client.get_workflow_handle(target_workflow_id)
        await handle.signal(signal_name)

    try:
        asyncio.run(_send())
        logger.info("Sent signal '%s' to workflow '%s'.", signal_name, target_workflow_id)
    except Exception as exc:
        logger.info(
            "Could not signal '%s' on workflow '%s' (%s) — probably not running; nothing to do.",
            signal_name,
            target_workflow_id,
            exc,
        )
