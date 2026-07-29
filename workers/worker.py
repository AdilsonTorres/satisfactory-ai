"""
workers/worker.py

HOST game worker — activity-only.

Runs the game-driving activities (screen capture, uinput, KWin focus) and
therefore MUST run directly on the desktop session, not in Docker. It
registers NO workflows: workflow tasks on the same queue are polled only by
the Dockerized orchestrator worker (workers/orchestrator.py) — Temporal
routes workflow tasks and activity tasks independently, so both workers
share one task queue without stepping on each other.

Prerequisite: docker compose up -d   (temporal + orchestrator worker)

How to run:
    uv run python workers/worker.py
(or install the systemd user service — see docs/deploy.md)

Runtime workflow control:
    temporal workflow signal --workflow-id <id> --name pause
    temporal workflow signal --workflow-id <id> --name resume
    temporal workflow signal --workflow-id <id> --name stop
    temporal workflow query  --workflow-id <id> --query-type get_stats
"""

import asyncio
import logging
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Worker

from activities import GAME_ACTIVITIES
from utils import config as cfg
from utils import logger as log

_logger = logging.getLogger(__name__)


def _is_fail_safe_key(key, configured_key_str: str) -> bool:
    try:
        from pynput import keyboard
    except ImportError:
        return False
    key_str = configured_key_str.lower().strip()

    if key_str.startswith("key."):
        key_name = key_str.split(".")[1]
        return bool(getattr(keyboard.Key, key_name, None) == key)

    special_map = {
        "f12": keyboard.Key.f12,
        "f11": keyboard.Key.f11,
        "f10": keyboard.Key.f10,
        "f9": keyboard.Key.f9,
        "esc": keyboard.Key.esc,
        "escape": keyboard.Key.esc,
        "pause": keyboard.Key.pause,
        "scroll_lock": keyboard.Key.scroll_lock,
    }
    if key_str in special_map:
        return bool(special_map[key_str] == key)

    char = getattr(key, "char", None)
    if char is not None:
        return bool(char.lower() == key_str)

    return False


async def emergency_stop(client: Client) -> None:
    _logger.warning("[FAIL-SAFE] Fail-safe key pressed! Pausing schedules and stopping workflows...")

    # Pause ALL gift-farm schedules first — otherwise the always-on schedule
    # would just restart the workflow on the next hourly tick, defeating the
    # purpose of the emergency stop. Run `schedule_gift_farm.py unpause` to
    # re-enable them after resolving the issue.
    try:
        async for s in await client.list_schedules():
            if s.id.startswith("gift-farm-"):
                try:
                    await client.get_schedule_handle(s.id).pause(note="paused by F9 fail-safe")
                    _logger.info("[FAIL-SAFE] Paused schedule: %s", s.id)
                except Exception as e:
                    _logger.error("[FAIL-SAFE] Error pausing schedule %s: %s", s.id, e)
    except Exception as exc:
        _logger.warning("[FAIL-SAFE] Could not list/pause schedules: %s", exc)

    # Signal all running workflows to stop gracefully.
    try:
        async for workflow_desc in client.list_workflows("ExecutionStatus = 'Running'"):
            try:
                handle = client.get_workflow_handle(workflow_desc.id)
                await handle.signal("stop")
                _logger.info("[FAIL-SAFE] Sent stop signal to workflow: %s", workflow_desc.id)
            except Exception as e:
                _logger.error("[FAIL-SAFE] Error signaling workflow %s: %s", workflow_desc.id, e)
    except Exception as exc:
        _logger.warning("[FAIL-SAFE] Could not list and signal workflows: %s", exc)

    _logger.warning("[FAIL-SAFE] Terminating host worker process now.")
    os._exit(1)


def start_fail_safe_listener(client: Client, loop: asyncio.AbstractEventLoop) -> None:
    try:
        from pynput import keyboard
    except ImportError:
        _logger.warning("pynput not installed. Global fail-safe keyboard listener disabled.")
        return

    fail_safe_key_str = cfg.get("input.fail_safe_key", "F9")

    def on_press(key) -> None:
        if _is_fail_safe_key(key, fail_safe_key_str):
            _logger.warning("!!! [FAIL-SAFE] Fail-safe hotkey detected!")
            asyncio.run_coroutine_threadsafe(emergency_stop(client), loop)

    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()
    _logger.info("Fail-safe global key listener active. Press [%s] at any time to emergency stop.", fail_safe_key_str)


async def main() -> None:
    log.setup(cfg.get("logging.level", "INFO"))

    address   = os.environ.get("TEMPORAL_ADDRESS") or cfg.get("temporal.address", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE") or cfg.get("temporal.namespace", "default")
    task_queue = cfg.get("temporal.task_queue", "satisfactory-bot")

    _logger.info("Connecting to Temporal at %s (ns=%s) ...", address, namespace)
    client = await Client.connect(address, namespace=namespace)
    _logger.info("Connected. Game-activity queue: '%s'", task_queue)

    loop = asyncio.get_running_loop()
    start_fail_safe_listener(client, loop)

    # Activities are sync (they drive the game with blocking sleeps/IO), so
    # they run on this executor instead of blocking the asyncio event loop —
    # a blocked loop would stall heartbeats and workflow task processing.
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="activity") as activity_executor:
        async with Worker(
            client,
            task_queue=task_queue,
            activities=GAME_ACTIVITIES,
            activity_executor=activity_executor,
            # Inputs are sequential — keep at 1 so actions in the game don't overlap
            max_concurrent_activities=1,
            identity=f"satisfactory-game-worker@{socket.gethostname()}",
            # On shutdown, give in-flight activities a cancellation notice and
            # this long to finish (e.g. close menus) before being dropped.
            graceful_shutdown_timeout=timedelta(seconds=10),
        ):
            _logger.info("Game worker active. UI: http://localhost:8233 | Ctrl+C to stop")
            await asyncio.Future()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
