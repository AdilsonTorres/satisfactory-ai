from typing import Any
from unittest.mock import patch

import pytest

from tools.cli import _resolve_item_interactive
from tools.late_game_planner import (
    ALL_RECIPES,
    generate_late_game_plan,
    generate_mermaid_flowchart,
    get_readable_name,
    validate_item_name,
)


def test_get_readable_name() -> None:
    assert get_readable_name("Desc_SteelPipe") == "Steel Pipe"
    assert get_readable_name("Desc_Motor") == "Motor"
    assert get_readable_name("Desc_Cement") == "Concrete"
    assert get_readable_name("Desc_SpaceElevatorPart9") == "Ballistic Warp Drive"
    assert get_readable_name("Desc_CustomItemName") == "Custom Item Name"


@patch("tools.late_game_planner.SatisfactorySave")
def test_generate_late_game_plan_simple(mock_save_class: Any) -> None:
    # Setup mock save object
    mock_save = mock_save_class.return_value
    mock_save.schematics = ["Schematic_Alternate_PureIronIngot"]
    mock_save.dimensional_depot = [
        {"name": "Desc_IronOre", "quantity": 1500},
        {"name": "Desc_IronPlate", "quantity": 800},
    ]

    # Generate a simple plan for 65 Iron Ingots/min, with overclocking
    plan = generate_late_game_plan(
        target_item="Iron Ingot", target_rate=65.0, overclock=True, sloop_items=set(), save_file_path="mock_save.sav"
    )

    assert plan["target_item"] == "Iron Ingot"
    assert plan["target_rate"] == 65.0
    assert plan["overclock"] is True
    assert "SAM" not in plan["raw_materials"]

    # Pure Iron Ingot uses 35 Iron Ore to make 65 Iron Ingot/min (Refinery)
    # Target rate is 65.0, so it matches exactly 1.0 Refinery machine needed.
    # Overclocked to 250%, so we need 1.0 / 2.5 = 0.4 machines.
    # Ceil of 0.4 = 1 machine built.
    # Shards needed: 1 machine * 3 = 3 shards.
    assert plan["total_shards"] == 3
    assert plan["total_sloops"] == 0

    # Depot comparison should contain Iron Ore
    assert "Iron Ore" in plan["depot_comparison"]
    assert plan["depot_comparison"]["Iron Ore"]["required_rate"] == 35.0
    assert plan["depot_comparison"]["Iron Ore"]["stored_qty"] == 1500


@patch("tools.late_game_planner.SatisfactorySave")
def test_generate_late_game_plan_with_sloops(mock_save_class: Any) -> None:
    # Setup mock save object
    mock_save = mock_save_class.return_value
    mock_save.schematics = ["Schematic_Alternate_PureIronIngot"]
    mock_save.dimensional_depot = []

    # Generate plan with Somersloops enabled on Iron Ingot
    # Output of Pure Iron Ingot is doubled (2x) by Somersloops.
    # Input required for target rate is halved, because output per input is doubled?
    # Wait, in plan_step:
    # base_output = 65, sloop_mult = 2, speed_mult = 2.5
    # output_per_machine = 65 * 2 * 2.5 = 325.0
    # machine_count = 65 / 325 = 0.2
    # input rate = input_rate_per_machine * (rate / (base_output * sloop_mult))
    # input_rate_per_machine = 35 Iron Ore, rate = 65, base_output = 65, sloop_mult = 2
    # required_input_rate = 35 * (65 / (65 * 2)) = 17.5 Iron Ore/min
    plan = generate_late_game_plan(
        target_item="Iron Ingot",
        target_rate=65.0,
        overclock=True,
        sloop_items={"Iron Ingot"},
        save_file_path="mock_save.sav",
    )

    assert plan["total_sloops"] == 2  # 1 Refinery built (ceil(0.2) = 1) * 2 sloop slots
    assert plan["depot_comparison"]["Iron Ore"]["required_rate"] == 17.5
    # Refinery base power = 30 MW
    # Overclocked power factor = 2.5^1.321928 = 3.3577
    # Somersloop power factor = 4.0
    # Power per machine = 30 * 3.3577 * 4.0 = 402.9 MW
    # Total power = 402.9 * 0.2 = 80.59 MW
    assert abs(plan["total_power_mw"] - 80.59) < 1.0


# --- validate_item_name tests ---

VALID_ITEMS = set(ALL_RECIPES.keys())


def test_validate_item_name_exact_match() -> None:
    """Exact match should pass without raising."""
    validate_item_name("Ballistic Warp Drive", VALID_ITEMS)
    validate_item_name("Iron Ingot", VALID_ITEMS)


def test_validate_item_name_typo_suggests_correction() -> None:
    """A close typo should raise ValueError with suggestions."""
    with pytest.raises(ValueError, match=r"Did you mean.*Ballistic Warp Drive"):
        validate_item_name("Ballist Warp Drive", VALID_ITEMS)


def test_validate_item_name_completely_unknown() -> None:
    """A completely unrelated string should raise ValueError without suggestions."""
    with pytest.raises(ValueError, match="is not recognised"):
        validate_item_name("ZZZZZZZZZZZZZ", VALID_ITEMS)


def test_validate_item_name_custom_label() -> None:
    """The label parameter should appear in the error message."""
    with pytest.raises(ValueError, match="Somersloop item 'Bad Name'"):
        validate_item_name("Bad Name", VALID_ITEMS, label="Somersloop item")


@patch("tools.late_game_planner.SatisfactorySave")
def test_generate_late_game_plan_rejects_typo(mock_save_class: Any) -> None:
    """generate_late_game_plan should reject a typo before parsing the save."""
    with pytest.raises(ValueError, match="Did you mean"):
        generate_late_game_plan(
            target_item="Ballist Warp Drive",
            target_rate=10.0,
            overclock=True,
            sloop_items=set(),
            save_file_path="mock_save.sav",
        )
    # Save file should never have been opened
    mock_save_class.assert_not_called()


@patch("tools.late_game_planner.SatisfactorySave")
def test_generate_late_game_plan_rejects_bad_sloop(mock_save_class: Any) -> None:
    """generate_late_game_plan should validate sloop item names too."""
    with pytest.raises(ValueError, match="Somersloop item"):
        generate_late_game_plan(
            target_item="Iron Ingot",
            target_rate=65.0,
            overclock=True,
            sloop_items={"Iron Ingott"},
            save_file_path="mock_save.sav",
        )
    mock_save_class.assert_not_called()


# --- _resolve_item_interactive tests ---


def test_resolve_interactive_exact_match() -> None:
    """Exact match should return immediately without prompting."""
    result = _resolve_item_interactive("Iron Ingot", VALID_ITEMS)
    assert result == "Iron Ingot"


@patch("builtins.input", return_value="y")
def test_resolve_interactive_single_suggestion_accept(mock_input: Any) -> None:
    """Single fuzzy match accepted by user should return the suggestion."""
    result = _resolve_item_interactive("Ballist Warp Drive", VALID_ITEMS)
    assert result == "Ballistic Warp Drive"
    mock_input.assert_called_once()


@patch("builtins.input", return_value="n")
def test_resolve_interactive_single_suggestion_decline(mock_input: Any) -> None:
    """User declining a single suggestion should exit."""
    with pytest.raises(SystemExit):
        _resolve_item_interactive("Ballist Warp Drive", VALID_ITEMS)


@patch("builtins.input", return_value="")
def test_resolve_interactive_single_suggestion_default_accept(mock_input: Any) -> None:
    """Pressing Enter (empty input) on a single suggestion should accept it."""
    result = _resolve_item_interactive("Ballist Warp Drive", VALID_ITEMS)
    assert result == "Ballistic Warp Drive"


def test_resolve_interactive_no_suggestions() -> None:
    """Completely unknown item with no fuzzy matches should exit."""
    with pytest.raises(SystemExit):
        _resolve_item_interactive("ZZZZZZZZZZZZZ", VALID_ITEMS)


@patch("builtins.input", return_value="1")
def test_resolve_interactive_multiple_suggestions_pick(mock_input: Any) -> None:
    """User picking from multiple suggestions should return the selected one."""
    # Use a small valid set that will produce multiple matches
    small_set = {"Iron Ingot", "Iron Rod", "Iron Plate", "Iron Ore"}
    result = _resolve_item_interactive("Iron", small_set, label="Item")
    assert result in small_set


@patch("builtins.input", return_value="0")
def test_resolve_interactive_multiple_suggestions_abort(mock_input: Any) -> None:
    """User picking 0 (abort) from multiple suggestions should exit."""
    small_set = {"Iron Ingot", "Iron Rod", "Iron Plate", "Iron Ore"}
    with pytest.raises(SystemExit):
        _resolve_item_interactive("Iron", small_set)


def test_resolve_interactive_acronym_match() -> None:
    """Exact uppercase acronym match should resolve directly without prompt."""
    assert _resolve_item_interactive("BWD", VALID_ITEMS) == "Ballistic Warp Drive"
    assert _resolve_item_interactive("SO", VALID_ITEMS) == "Superposition Oscillator"
    assert _resolve_item_interactive("DMC", VALID_ITEMS) == "Dark Matter Crystal"
    assert _resolve_item_interactive("TPR", VALID_ITEMS) == "Thermal Propulsion Rocket"


# --- Build guide tests ---


@patch("tools.late_game_planner.SatisfactorySave")
def test_build_guide_exists_in_plan(mock_save_class: Any) -> None:
    """Plan output should include a build_guide key with phases."""
    mock_save = mock_save_class.return_value
    mock_save.schematics = []
    mock_save.dimensional_depot = []

    plan = generate_late_game_plan(
        target_item="Iron Ingot",
        target_rate=65.0,
        overclock=True,
        sloop_items=set(),
        save_file_path="mock_save.sav",
    )

    assert "build_guide" in plan
    guide = plan["build_guide"]
    assert "phases" in guide
    assert "inline_items" in guide
    assert "dedicated_items" in guide
    assert "co_location_groups" in guide
    assert len(guide["phases"]) >= 1


@patch("tools.late_game_planner.SatisfactorySave")
def test_build_guide_phase_ordering(mock_save_class: Any) -> None:
    """Phases should be ordered by depth, with raw extraction last."""
    mock_save = mock_save_class.return_value
    mock_save.schematics = ["Schematic_Alternate_PureIronIngot"]
    mock_save.dimensional_depot = []

    plan = generate_late_game_plan(
        target_item="Iron Ingot",
        target_rate=65.0,
        overclock=True,
        sloop_items=set(),
        save_file_path="mock_save.sav",
    )

    phases = plan["build_guide"]["phases"]
    # Phase numbers should be sequential
    phase_numbers = [p["phase"] for p in phases]
    assert phase_numbers == list(range(1, len(phases) + 1))

    # Last phase should be raw extraction
    assert phases[-1]["name"] == "Raw Extraction"
    assert phases[-1]["depth"] == -1


@patch("tools.late_game_planner.SatisfactorySave")
def test_build_guide_depth_tracking(mock_save_class: Any) -> None:
    """Steps should carry depth metadata; target item should be depth 0."""
    mock_save = mock_save_class.return_value
    mock_save.schematics = []
    mock_save.dimensional_depot = []

    plan = generate_late_game_plan(
        target_item="Modular Frame",
        target_rate=10.0,
        overclock=False,
        sloop_items=set(),
        save_file_path="mock_save.sav",
    )

    # The target item step should have depth 0
    target_steps = [s for s in plan["steps"] if s["item"] == "Modular Frame"]
    assert len(target_steps) == 1
    assert target_steps[0]["depth"] == 0

    # All steps should have a depth field >= 0
    for step in plan["steps"]:
        assert "depth" in step
        assert step["depth"] >= 0


@patch("tools.late_game_planner.SatisfactorySave")
def test_generate_late_game_plan_ballistic_warp_drive(mock_save_class: Any) -> None:
    """Test full Ballistic Warp Drive planning, verifying Superposition Oscillator rates and Dark Matter Crystal machine type."""
    mock_save = mock_save_class.return_value
    mock_save.schematics = ["Schematic_Alternate_DarkMatter_Trap"]
    mock_save.recipes = []
    mock_save.dimensional_depot = []

    plan = generate_late_game_plan(
        target_item="Ballistic Warp Drive",
        target_rate=10.0,
        overclock=True,
        sloop_items=set(),
        save_file_path="mock_save.sav",
        recipe_multiplier=0.75,
    )

    # 1. Verify Superposition Oscillator step
    so_steps = [s for s in plan["steps"] if s["item"] == "Superposition Oscillator"]
    assert len(so_steps) == 1
    so_step = so_steps[0]
    # Rate: 10 * 2 (base input) * 0.75 (multiplier) = 15.0
    assert so_step["rate"] == 15.0
    # Output per machine at 250% speed: 5.0 * 2.5 = 12.5
    assert so_step["output_per_machine"] == 12.5
    # Machine count: 15.0 / 12.5 = 1.2
    assert abs(so_step["machine_count"] - 1.2) < 1e-6

    # 2. Verify Dark Matter Crystal step using alternate recipe (Dark Matter Trap) in Particle Accelerator
    dmc_steps = [s for s in plan["steps"] if s["item"] == "Dark Matter Crystal"]
    assert len(dmc_steps) == 1
    dmc_step = dmc_steps[0]
    assert dmc_step["recipe_name"] == "Dark Matter Trap"
    assert dmc_step["machine"] == "Particle Accelerator"


@patch("tools.late_game_planner.SatisfactorySave")
def test_generate_late_game_plan_locked_recipe_fallback(mock_save_class: Any) -> None:
    """When the best alternate is locked, the planner falls back to the default recipe silently (no warning)."""
    mock_save = mock_save_class.return_value
    # No alternate schematics or recipes unlocked
    mock_save.schematics = []
    mock_save.recipes = []
    mock_save.dimensional_depot = []

    plan = generate_late_game_plan(
        target_item="Ballistic Warp Drive",
        target_rate=10.0,
        overclock=True,
        sloop_items=set(),
        save_file_path="mock_save.sav",
        recipe_multiplier=0.75,
    )

    # No LOCKED warnings expected — locked alternates are silently replaced by defaults.
    # Byproduct clock-speed warnings are still emitted (that is the intended behavior).
    locked_warnings = [w for w in plan["warnings"] if "locked" in w.lower()]
    assert locked_warnings == []

    # Dark Matter Crystal should fall back to the default recipe (Converter), not Dark Matter Trap
    dmc_steps = [s for s in plan["steps"] if s["item"] == "Dark Matter Crystal"]
    assert len(dmc_steps) == 1
    assert dmc_steps[0]["recipe_name"] != "Dark Matter Trap"  # best was locked; default used


def test_generate_mermaid_flowchart_late_game() -> None:

    chart = generate_mermaid_flowchart(
        target_item="Iron Ingot",
        target_rate=65.0,
        unlocked_schematics=set(),
        sloop_items={"Iron Ingot"},
        overclock=True,
        recipe_multiplier=0.75,
    )
    assert "flowchart TD" in chart
    assert "Iron Ore" in chart
    assert "Sloop 2x" in chart


@patch("tools.late_game_planner.SatisfactorySave")
def test_byproduct_overflow_and_disposal(mock_save_class: Any) -> None:
    """Verify that byproduct overflow is balanced and converted to sinkable items."""
    mock_save = mock_save_class.return_value
    mock_save.schematics = ["Schematic_Alternate_DarkMatter_Trap"]
    mock_save.recipes = []
    mock_save.dimensional_depot = []

    # AI Expansion Server generates a net overflow of Dark Matter Residue (220.0 produced, 60.0 consumed).
    # Net overflow = 160.0 m3/min.
    # This should trigger disposal of 160.0 m3/min Dark Matter Residue into Dark Matter Crystals.
    plan = generate_late_game_plan(
        target_item="AI Expansion Server",
        target_rate=4.0,
        overclock=True,
        sloop_items=set(),
        save_file_path="mock_save.sav",
        recipe_multiplier=1.0,
    )

    # Check that we have a Dark Matter Crystal step for disposal (total crystals rate includes 24.0 consumed + 96.0 disposed = 120.0)
    dmc_steps = [s for s in plan["steps"] if s["item"] == "Dark Matter Crystal"]
    assert len(dmc_steps) == 1
    assert abs(dmc_steps[0]["rate"] - 120.0) < 1e-4


@patch("tools.late_game_planner.SatisfactorySave")
def test_bwd_byproduct_overflow_and_disposal(mock_save_class: Any) -> None:
    """Verify that under BWD @ 10/min, sloop BWD, multiplier 0.75, with empty unlocks, Heavy Oil Residue overflows and is converted to Petroleum Coke."""
    mock_save = mock_save_class.return_value
    mock_save.schematics = []
    mock_save.recipes = []
    mock_save.dimensional_depot = []

    plan = generate_late_game_plan(
        target_item="Ballistic Warp Drive",
        target_rate=10.0,
        overclock=True,
        sloop_items={"Ballistic Warp Drive"},
        save_file_path="mock_save.sav",
        recipe_multiplier=0.75,
    )

    # Petroleum Coke disposal step should be present
    coke_steps = [s for s in plan["steps"] if s["item"] == "Petroleum Coke"]
    assert len(coke_steps) == 1
    # Check that rate of coke is greater than 0
    assert coke_steps[0]["rate"] > 0.0

    # Check that Petroleum Coke is in the build guide phases
    phases = plan["build_guide"]["phases"]
    found_coke = False
    for phase in phases:
        phase_num = phase["depth"]
        for item in phase["items"]:
            if item["item"] == "Petroleum Coke":
                found_coke = True
                assert phase_num >= 3
    assert found_coke is True


@patch("tools.late_game_planner.SatisfactorySave")
def test_bwd_planner_exact_machine_counts_and_phase_isolation(mock_save_class: Any) -> None:
    """Verify exact machine counts and phase depth isolation for Ballistic Warp Drive (10/min, 0.75 mult, overclock, slopped BWD)."""
    mock_save = mock_save_class.return_value
    mock_save.schematics = []
    mock_save.recipes = []
    mock_save.dimensional_depot = []

    plan = generate_late_game_plan(
        target_item="Ballistic Warp Drive",
        target_rate=10.0,
        overclock=True,
        sloop_items={"Ballistic Warp Drive"},
        save_file_path="mock_save.sav",
        recipe_multiplier=0.75,
    )

    # 1. Target BWD step check
    bwd_steps = [s for s in plan["steps"] if s["item"] == "Ballistic Warp Drive"]
    assert len(bwd_steps) == 1
    bwd = bwd_steps[0]
    assert bwd["machine"] == "Manufacturer"
    assert abs(bwd["machine_count"] - 2.00) < 1e-3
    assert abs(bwd["rate"] - 10.0) < 1e-3
    assert bwd["depth"] == 0

    # 2. Phase 1 (depth 0) isolation check
    depth_0_steps = [s for s in plan["steps"] if s["depth"] == 0]
    assert len(depth_0_steps) == 1
    assert depth_0_steps[0]["item"] == "Ballistic Warp Drive"

    # 4. Superposition Oscillator byproduct check
    so_steps = [s for s in plan["steps"] if s["item"] == "Superposition Oscillator"]
    assert len(so_steps) == 1
    so = so_steps[0]
    assert "Dark Matter Residue" in so.get("byproducts", {})

    # 5. No alternate badge when no alternates are unlocked
    for step in plan["steps"]:
        assert "alternate" in step  # field must always be present
    bwd_step = bwd_steps[0]
    assert bwd_step["alternate"] is False  # standard recipe, not alternate


@patch("tools.late_game_planner.SatisfactorySave")
def test_unsinkable_fluid_capacity_warnings(mock_save_class: Any) -> None:
    """Verify that ONLY primary liquid items get clock speed capacity warnings."""
    mock_save = mock_save_class.return_value
    mock_save.schematics = ["Schematic_Alternate_DarkMatter_Trap"]
    mock_save.recipes = []
    mock_save.dimensional_depot = []

    plan = generate_late_game_plan(
        target_item="Ballistic Warp Drive",
        target_rate=10.0,
        overclock=True,
        sloop_items={"Ballistic Warp Drive"},
        save_file_path="mock_save.sav",
        recipe_multiplier=0.75,
    )

    warnings = plan["warnings"]

    # Dark Matter Residue (primary fluid) is un-sinkable, so it gets a warning!
    dmr_warnings = [w for w in warnings if "Dark Matter Residue" in w and "clock speed" in w]
    assert len(dmr_warnings) == 1
    assert "83.9%" in dmr_warnings[0]

    # Superposition Oscillator (primary solid) CAN be sinked, NO warning!
    so_warnings = [w for w in warnings if "Superposition Oscillator" in w]
    assert len(so_warnings) == 0

    # Rubber (primary solid) CAN be sinked, NO warning!
    rubber_warnings = [w for w in warnings if "Rubber" in w]
    assert len(rubber_warnings) == 0

    # Aluminum Scrap (primary solid) CAN be sinked, NO warning!
    scrap_warnings = [w for w in warnings if "Aluminum Scrap" in w]
    assert len(scrap_warnings) == 0
