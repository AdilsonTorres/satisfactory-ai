"""
tests/test_recipe_db.py

TDD tests for recipe definitions, machine assignments, input/output rates,
and alternate recipes in utils/recipe_db.py.
"""

from utils.recipe_db import RECIPES

VALID_MACHINES = {
    "Smelter",
    "Foundry",
    "Constructor",
    "Assembler",
    "Manufacturer",
    "Refinery",
    "Blender",
    "Particle Accelerator",
    "Quantum Encoder",
    "Converter",
    "Packager",
}


def test_bwd_recipe_machine_and_inputs() -> None:
    """Verify Ballistic Warp Drive uses Manufacturer and 4 solid inputs."""
    assert "Ballistic Warp Drive" in RECIPES
    bwd = RECIPES["Ballistic Warp Drive"]

    assert bwd["default"]["machine"] == "Manufacturer"
    assert bwd["best"]["machine"] == "Manufacturer"

    default_inputs = bwd["default"]["inputs"]
    assert default_inputs["Thermal Propulsion Rocket"] == 1.0
    assert default_inputs["Singularity Cell"] == 5.0
    assert default_inputs["Superposition Oscillator"] == 2.0
    assert default_inputs["Dark Matter Crystal"] == 40.0
    assert "Excited Photonic Matter" not in default_inputs

    default_outputs = bwd["default"]["outputs"]
    assert default_outputs["Ballistic Warp Drive"] == 1.0
    assert "Dark Matter Residue" not in default_outputs


def test_singularity_cell_output_rate() -> None:
    """Verify Singularity Cell outputs 10.0 per minute at 100% clock speed."""
    assert "Singularity Cell" in RECIPES
    sc = RECIPES["Singularity Cell"]

    assert sc["default"]["outputs"]["Singularity Cell"] == 10.0
    assert sc["best"]["outputs"]["Singularity Cell"] == 10.0


def test_quantum_encoder_recipes() -> None:
    """Verify Phase 5 Quantum Encoder items specify Quantum Encoder as their machine."""
    quantum_items = [
        "Superposition Oscillator",
        "Neural-Quantum Processor",
        "AI Expansion Server",
    ]
    for item in quantum_items:
        assert item in RECIPES, f"Missing recipe for {item}"
        recipe = RECIPES[item]["default"]
        assert recipe["machine"] == "Quantum Encoder", f"{item} should use Quantum Encoder, got {recipe['machine']}"


def test_dark_matter_crystal_recipes() -> None:
    """Verify default DMC recipe is in Converter and alternate Dark Matter Trap is in Particle Accelerator."""
    assert "Dark Matter Crystal" in RECIPES
    dmc = RECIPES["Dark Matter Crystal"]

    assert dmc["default"]["machine"] == "Converter"
    assert dmc["default"]["outputs"]["Dark Matter Crystal"] == 30.0
    assert dmc["default"]["inputs"]["Diamond"] == 30.0
    assert dmc["default"]["inputs"]["Dark Matter Residue"] == 150.0

    assert dmc["best"]["machine"] == "Particle Accelerator"
    assert dmc["best"]["name"] == "Dark Matter Trap"
    assert dmc["best"]["outputs"]["Dark Matter Crystal"] == 60.0
    assert dmc["best"]["inputs"]["Time Crystal"] == 30.0
    assert dmc["best"]["inputs"]["Dark Matter Residue"] == 150.0


def test_phase5_quantum_recipes_integrity() -> None:
    """Verify machine types and output rates for Phase 5 end-game components."""
    # Singularity Cell
    sc = RECIPES["Singularity Cell"]["default"]
    assert sc["machine"] == "Manufacturer"
    assert sc["outputs"]["Singularity Cell"] == 10.0
    assert sc["inputs"]["Nuclear Pasta"] == 1.0
    assert sc["inputs"]["Dark Matter Crystal"] == 20.0

    # Superposition Oscillator
    so = RECIPES["Superposition Oscillator"]["default"]
    assert so["machine"] == "Quantum Encoder"
    assert so["outputs"]["Superposition Oscillator"] == 5.0
    assert so["outputs"]["Dark Matter Residue"] == 125.0

    # Neural-Quantum Processor
    nqp = RECIPES["Neural-Quantum Processor"]["default"]
    assert nqp["machine"] == "Quantum Encoder"
    assert nqp["outputs"]["Neural-Quantum Processor"] == 3.0
    assert nqp["outputs"]["Dark Matter Residue"] == 75.0

    # AI Expansion Server
    aes = RECIPES["AI Expansion Server"]["default"]
    assert aes["machine"] == "Quantum Encoder"
    assert aes["outputs"]["AI Expansion Server"] == 4.0
    assert aes["outputs"]["Dark Matter Residue"] == 100.0


def test_all_recipes_have_valid_machines() -> None:
    """Verify all defined recipes use valid Satisfactory production machines."""
    for item, variants in RECIPES.items():
        for variant_key, recipe in variants.items():
            machine = recipe.get("machine")
            assert machine in VALID_MACHINES, f"Invalid machine '{machine}' for item '{item}' variant '{variant_key}'"


def test_all_recipe_rates_positive() -> None:
    """Verify input and output quantities for all recipes are positive floats."""
    for item, variants in RECIPES.items():
        for variant_key, recipe in variants.items():
            for inp_name, rate in recipe.get("inputs", {}).items():
                assert rate > 0.0, f"Non-positive input rate {rate} for {inp_name} in {item} ({variant_key})"
            for out_name, rate in recipe.get("outputs", {}).items():
                assert rate > 0.0, f"Non-positive output rate {rate} for {out_name} in {item} ({variant_key})"


def test_all_recipes_structure_and_ratios() -> None:
    """Verify every item in RECIPES has valid default/best variants, output matching item name, and valid machines."""
    raw_nodes = {
        "Raw Quartz",
        "Coal",
        "Iron Ore",
        "Copper Ore",
        "Caterium Ore",
        "Bauxite",
        "SAM",
        "Crude Oil",
        "Water",
        "Excited Photonic Matter",
    }
    for item, variants in RECIPES.items():
        assert "default" in variants, f"{item} missing default variant"
        assert "best" in variants, f"{item} missing best variant"

        for vkey in ["default", "best"]:
            recipe = variants[vkey]
            assert recipe.get("name"), f"Missing name for {item}.{vkey}"
            assert recipe.get("machine") in VALID_MACHINES, f"Invalid machine for {item}.{vkey}"
            outputs = recipe.get("outputs", {})
            assert item in outputs, f"Target item '{item}' missing from outputs of {item}.{vkey}"
            assert outputs[item] > 0.0, f"Non-positive output for {item}.{vkey}"

            inputs = recipe.get("inputs", {})
            if item not in raw_nodes:
                assert len(inputs) > 0, f"Non-raw item '{item}.{vkey}' has empty inputs"
