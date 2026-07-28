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


def test_bwd_recipe_machine_and_inputs():
    """Verify Ballistic Warp Drive uses Quantum Encoder and accurate 1.0 inputs/outputs."""
    assert "Ballistic Warp Drive" in RECIPES
    bwd = RECIPES["Ballistic Warp Drive"]

    assert bwd["default"]["machine"] == "Quantum Encoder"
    assert bwd["best"]["machine"] == "Quantum Encoder"

    default_inputs = bwd["default"]["inputs"]
    assert default_inputs["Thermal Propulsion Rocket"] == 1.0
    assert default_inputs["Singularity Cell"] == 5.0
    assert default_inputs["Superposition Oscillator"] == 2.0
    assert default_inputs["Dark Matter Crystal"] == 40.0
    assert default_inputs["Excited Photonic Matter"] == 250.0

    default_outputs = bwd["default"]["outputs"]
    assert default_outputs["Ballistic Warp Drive"] == 1.0
    assert default_outputs["Dark Matter Residue"] == 250.0


def test_singularity_cell_output_rate():
    """Verify Singularity Cell outputs 1.0 per minute at 100% clock speed."""
    assert "Singularity Cell" in RECIPES
    sc = RECIPES["Singularity Cell"]

    assert sc["default"]["outputs"]["Singularity Cell"] == 1.0
    assert sc["best"]["outputs"]["Singularity Cell"] == 1.0


def test_quantum_encoder_recipes():
    """Verify Phase 5 Quantum Encoder items specify Quantum Encoder as their machine."""
    quantum_items = [
        "Superposition Oscillator",
        "Neural-Quantum Processor",
        "AI Expansion Server",
        "Ballistic Warp Drive",
    ]
    for item in quantum_items:
        assert item in RECIPES, f"Missing recipe for {item}"
        recipe = RECIPES[item]["default"]
        assert (
            recipe["machine"] == "Quantum Encoder"
        ), f"{item} should use Quantum Encoder, got {recipe['machine']}"


def test_all_recipes_have_valid_machines():
    """Verify all defined recipes use valid Satisfactory production machines."""
    for item, variants in RECIPES.items():
        for variant_key, recipe in variants.items():
            machine = recipe.get("machine")
            assert (
                machine in VALID_MACHINES
            ), f"Invalid machine '{machine}' for item '{item}' variant '{variant_key}'"


def test_all_recipe_rates_positive():
    """Verify input and output quantities for all recipes are positive floats."""
    for item, variants in RECIPES.items():
        for variant_key, recipe in variants.items():
            for inp_name, rate in recipe.get("inputs", {}).items():
                assert (
                    rate > 0.0
                ), f"Non-positive input rate {rate} for {inp_name} in {item} ({variant_key})"
            for out_name, rate in recipe.get("outputs", {}).items():
                assert (
                    rate > 0.0
                ), f"Non-positive output rate {rate} for {out_name} in {item} ({variant_key})"
