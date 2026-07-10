"""
activities/records.py

Persistence activities. These do NOT touch the game or the screen, so they
run on the persist task queue served by the Dockerized orchestrator worker
(stats/ is a bind mount there) — not on the host game worker.
"""

import logging

from temporalio import activity

from utils import gift_db

logger = logging.getLogger(__name__)


@activity.defn
def record_gift_check(result: dict) -> None:
    """
    Persist one doggo gift check (collected or empty) to stats/gift_history.db.

    `result` is what collect_doggo_gift returned:
        {doggo, collected, item, slot_diff, crop_path, checked_at}
    """
    gift_db.record_check(
        doggo=result["doggo"],
        collected=bool(result.get("collected")),
        item=result.get("item"),
        slot_diff=result.get("slot_diff"),
        crop_path=result.get("crop_path"),
        ts=result.get("checked_at"),
    )
    logger.info(
        "Recorded gift check: doggo=%s collected=%s item=%s",
        result["doggo"],
        result.get("collected"),
        result.get("item"),
    )
