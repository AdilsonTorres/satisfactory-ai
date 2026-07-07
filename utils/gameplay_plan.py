"""
utils/gameplay_plan.py

Pure data-assembly functions for `sbot plan` — merges the save parser
(utils/save_parser.py) and the alternate recipe advisor
(utils/alternate_advisor.py) into a single "what should I do next" report.

No argparse, no printing — tools/cli.py owns presentation, same split as
save_parser.py/alternate_advisor.py already use.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from utils.alternate_advisor import get_recipe_recommendations

GUIDE_DOC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "game_design_guides.md"
)
_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def build_milestone_summary(save: Any) -> dict[str, Any]:
    return {
        "game_phase": save.game_phase,
        "active_schematic": save.metadata.get("active_schematic"),
        "purchased_schematics_count": len(save.schematics),
        "hard_drives_unlocked": save.hard_drives_unlocked,
    }


def build_recipe_recommendations(save: Any) -> dict[str, Any]:
    result: dict[str, Any] = get_recipe_recommendations(save.schematics)
    return result


def build_resource_status(save: Any) -> dict[str, Any]:
    coupons_available = 0
    total_earned = 0
    if save.resource_sink:
        coupons_available = save.resource_sink.get("coupons_available") or 0
        total_earned = (save.resource_sink.get("coupons_earned_items") or 0) + (
            save.resource_sink.get("coupons_earned_dna") or 0
        )
    return {
        "coupons_available": coupons_available,
        "total_coupons_earned": total_earned,
        "dimensional_depot_item_types": len(save.dimensional_depot),
    }


def build_factory_snapshot(save: Any) -> dict[str, Any]:
    return {
        "producers": sum(save.factory_producers.values()),
        "extractors": sum(save.factory_extractors.values()),
        "generators": sum(save.factory_generators.values()),
        "batteries": save.factory_batteries,
    }


def load_save_history(history_path: str) -> list[dict[str, Any]]:
    if not os.path.exists(history_path):
        return []
    try:
        with open(history_path, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def build_progress_delta(save: Any, history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Diffs against the most recent history entry that isn't this same save
    (matched by session_name + play_duration_seconds)."""
    current_duration = save.header.get("play_duration_seconds", 0)
    session_name = save.header.get("session_name")
    candidates = [
        h
        for h in history
        if not (h.get("session_name") == session_name and h.get("play_duration_seconds") == current_duration)
    ]
    if not candidates:
        return None
    prior = max(candidates, key=lambda h: h.get("play_duration_seconds", 0))

    coupons_now = 0
    if save.resource_sink:
        coupons_now = (save.resource_sink.get("coupons_earned_items") or 0) + (
            save.resource_sink.get("coupons_earned_dna") or 0
        )

    return {
        "prior_timestamp": prior.get("timestamp"),
        "hours_played_delta": (current_duration - prior.get("play_duration_seconds", 0)) // 3600,
        "recipes_delta": len(save.recipes) - prior.get("unlocked_recipes_count", 0),
        "alternates_delta": save.alternate_recipes_unlocked - prior.get("alternate_recipes_unlocked", 0),
        "coupons_earned_delta": coupons_now - prior.get("total_coupons_earned", 0),
        "producers_delta": sum(save.factory_producers.values()) - prior.get("producers_count", 0),
    }


def get_guide_section_pointers(doc_path: str = GUIDE_DOC_PATH) -> list[str]:
    """Table of contents for docs/game_design_guides.md — extracts '## '
    headings at call time so it self-updates as the doc changes. Excludes the
    alternate-recipe section since that content is already shown verbatim via
    build_recipe_recommendations()."""
    if not os.path.exists(doc_path):
        return []
    with open(doc_path, encoding="utf-8") as f:
        text = f.read()
    return [h for h in _HEADING_RE.findall(text) if "alternate recipe" not in h.lower()]


def build_gameplay_plan(save: Any, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    history = history or []
    return {
        "milestone": build_milestone_summary(save),
        "recipes": build_recipe_recommendations(save),
        "resources": build_resource_status(save),
        "factory": build_factory_snapshot(save),
        "delta": build_progress_delta(save, history),
        "guide_sections": get_guide_section_pointers(),
        "guide_doc_path": GUIDE_DOC_PATH,
    }
