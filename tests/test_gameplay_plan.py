import json

from utils.alternate_advisor import get_recipe_recommendations
from utils.gameplay_plan import (
    build_factory_snapshot,
    build_gameplay_plan,
    build_milestone_summary,
    build_progress_delta,
    build_recipe_recommendations,
    build_resource_status,
    get_guide_section_pointers,
    load_save_history,
)
from utils.save_parser import SatisfactorySave


def _base_save():
    save = object.__new__(SatisfactorySave)
    save.header = {"session_name": "Chilling", "play_duration_seconds": 3600}
    save.game_phase = "GP_Project_Assembly_Phase_3"
    save.metadata = {"active_schematic": "Schematic_Tier5_1"}
    save.schematics = ["Schematic_Tier1_1", "Schematic_Alternate_PureIronIngot"]
    save.hard_drives_unlocked = 3
    save.recipes = ["Recipe_Screw", "Recipe_Alternate_Screw"]
    save.alternate_recipes_unlocked = 1
    save.resource_sink = {
        "coupons_available": 2,
        "coupons_earned_items": 10,
        "coupons_earned_dna": 1,
    }
    save.dimensional_depot = [{"name": "Desc_IronPlate", "quantity": 42}]
    save.factory_producers = {"Build_AssemblerMk1_C": 5}
    save.factory_extractors = {"Build_MinerMk1_C": 3}
    save.factory_generators = {"Build_GeneratorCoal_C": 2}
    save.factory_batteries = 1
    return save


def test_build_milestone_summary():
    save = _base_save()
    result = build_milestone_summary(save)
    assert result == {
        "game_phase": "GP_Project_Assembly_Phase_3",
        "active_schematic": "Schematic_Tier5_1",
        "purchased_schematics_count": 2,
        "hard_drives_unlocked": 3,
    }


def test_build_recipe_recommendations_delegates():
    save = _base_save()
    assert build_recipe_recommendations(save) == get_recipe_recommendations(save.schematics)


def test_build_resource_status_with_sink():
    save = _base_save()
    result = build_resource_status(save)
    assert result == {
        "coupons_available": 2,
        "total_coupons_earned": 11,
        "dimensional_depot_item_types": 1,
    }


def test_build_resource_status_no_sink():
    save = _base_save()
    save.resource_sink = None
    save.dimensional_depot = []
    result = build_resource_status(save)
    assert result == {
        "coupons_available": 0,
        "total_coupons_earned": 0,
        "dimensional_depot_item_types": 0,
    }


def test_build_factory_snapshot():
    save = _base_save()
    assert build_factory_snapshot(save) == {
        "producers": 5,
        "extractors": 3,
        "generators": 2,
        "batteries": 1,
    }


def test_load_save_history_missing_file(tmp_path):
    assert load_save_history(str(tmp_path / "nope.json")) == []


def test_load_save_history_corrupt_json(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("not json", encoding="utf-8")
    assert load_save_history(str(path)) == []


def test_build_progress_delta_no_history():
    save = _base_save()
    assert build_progress_delta(save, []) is None


def test_build_progress_delta_only_self_entry():
    save = _base_save()
    history = [
        {
            "session_name": "Chilling",
            "play_duration_seconds": 3600,
        }
    ]
    assert build_progress_delta(save, history) is None


def test_build_progress_delta_with_prior():
    save = _base_save()
    history = [
        {
            "timestamp": "2026-07-01T00:00:00",
            "session_name": "Chilling",
            "play_duration_seconds": 0,
            "unlocked_recipes_count": 1,
            "alternate_recipes_unlocked": 0,
            "total_coupons_earned": 5,
            "producers_count": 2,
        }
    ]
    delta = build_progress_delta(save, history)
    assert delta == {
        "prior_timestamp": "2026-07-01T00:00:00",
        "hours_played_delta": 1,
        "recipes_delta": 1,
        "alternates_delta": 1,
        "coupons_earned_delta": 6,
        "producers_delta": 3,
    }


def test_get_guide_section_pointers_reads_real_doc():
    headings = get_guide_section_pointers()
    assert len(headings) == 3
    assert not any("alternate recipe" in h.lower() for h in headings)


def test_get_guide_section_pointers_missing_doc(tmp_path):
    assert get_guide_section_pointers(str(tmp_path / "nope.md")) == []


def test_build_gameplay_plan_aggregates():
    save = _base_save()
    history = [
        {
            "timestamp": "2026-07-01T00:00:00",
            "session_name": "Chilling",
            "play_duration_seconds": 0,
            "unlocked_recipes_count": 0,
            "alternate_recipes_unlocked": 0,
            "total_coupons_earned": 0,
            "producers_count": 0,
        }
    ]
    plan = build_gameplay_plan(save, history)
    assert set(plan.keys()) == {
        "milestone",
        "recipes",
        "resources",
        "factory",
        "delta",
        "guide_sections",
        "guide_doc_path",
    }
    assert plan["delta"] is not None


def test_load_save_history_roundtrip(tmp_path):
    path = tmp_path / "history.json"
    data = [{"session_name": "X", "play_duration_seconds": 10}]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert load_save_history(str(path)) == data
