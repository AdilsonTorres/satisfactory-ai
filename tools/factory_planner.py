import math
from typing import Any

from utils.recipe_db import RECIPES, SINK_POINTS
from utils.save_parser import SatisfactorySave


def get_coupon_point_cost(current_coupons: int) -> int:
    """Calculates point cost of the next coupon using the quadratic scaling formula."""
    # Points = 500 * (ceil((n + 1) / 3) - 1)^2 + 1000
    n = current_coupons + 1
    ceil_val = math.ceil(n / 3)
    return 500 * ((ceil_val - 1) ** 2) + 1000


def plan_factory_step(
    item: str, rate: float, unlocked_schematics: set[str], steps: list[dict[str, Any]], raw_materials: dict[str, float]
):
    """Recursively traces production tree using the best alternate recipes."""
    # If it is a raw resource (no recipes exist for it), add to raw materials and stop
    if item not in RECIPES:
        raw_materials[item] = raw_materials.get(item, 0.0) + rate
        return

    # Determine which recipe to use; fall back to default silently if best is locked
    recipe_dict = RECIPES[item]
    best = recipe_dict.get("best")
    default = recipe_dict["default"]

    if best and best.get("alternate") and best.get("schematic"):
        schem_name = best["schematic"]
        # Extra robustness for 1.0 diamond/aluminum renames
        unlocked = schem_name in unlocked_schematics
        if schem_name == "Schematic_Alternate_AluminumBeam":
            unlocked = unlocked or "Schematic_Alternate_SteelBeam_Aluminum" in unlocked_schematics
        elif schem_name == "Schematic_Alternate_Diamond_OilBased":
            unlocked = unlocked or "Schematic_Alternate_Diamond_Petroleum" in unlocked_schematics
        elif schem_name == "Schematic_Alternate_Diamond_Pink":
            unlocked = unlocked or "Schematic_Alternate_Diamond_Cloudy" in unlocked_schematics
        recipe = best if unlocked else default
    else:
        recipe = best or default

    is_unlocked = True  # selected recipe is always usable
    output_rate = recipe["outputs"][item]
    machine_count = rate / output_rate

    steps.append(
        {
            "item": item,
            "rate": rate,
            "recipe_name": recipe["name"],
            "machine": recipe["machine"],
            "machine_count": machine_count,
            "unlocked": is_unlocked,
            "alternate": recipe.get("alternate", False),
        }
    )

    # Recursively trace inputs
    for input_item, input_rate_per_machine in recipe["inputs"].items():
        required_input_rate = input_rate_per_machine * machine_count
        plan_factory_step(input_item, required_input_rate, unlocked_schematics, steps, raw_materials)


def generate_production_plan(
    target_item: str | None, target_rate: float | None, coupons_per_minute: float | None, save_file_path: str
) -> dict[str, Any]:
    """Generates the full factory production plan."""
    # 1. Parse save file to get unlocked schematics and coupon count
    save = SatisfactorySave(save_file_path)
    # mPurchasedSchematics (milestones) + mAvailableRecipes (MAM hard-drive unlocks).
    # mAvailableRecipes uses "Recipe_Alternate_X"; recipe_db keys use "Schematic_Alternate_X".
    unlocked_schematics = set(save.schematics) | {
        r.replace("Recipe_Alternate_", "Schematic_Alternate_", 1)
        for r in save.recipes
        if r.startswith("Recipe_Alternate_")
    }
    current_coupons = save.resource_sink.get("coupons_earned_items", 0)

    # 2. Determine target item and rate
    warnings = []
    points_required = 0.0

    if coupons_per_minute is not None and coupons_per_minute > 0:
        # Calculate required points
        points_per_coupon = get_coupon_point_cost(current_coupons)
        points_required = coupons_per_minute * points_per_coupon

        # Target Thermal Propulsion Rocket (best points density)
        tpr_points = SINK_POINTS["Thermal Propulsion Rocket"]
        target_item = "Thermal Propulsion Rocket"
        target_rate = points_required / tpr_points

    if not target_item or not target_rate:
        raise ValueError("Must specify either a target item and rate, or coupons per minute.")

    if target_item not in RECIPES:
        import difflib

        suggestions = difflib.get_close_matches(target_item, RECIPES.keys(), n=5, cutoff=0.45)
        msg = f"Target item '{target_item}' is not recognised in the recipe database."
        if suggestions:
            formatted = ", ".join(f"'{s}'" for s in suggestions)
            msg += f" Did you mean: {formatted}?"
        raise ValueError(msg)

    # 3. Recursively generate tree steps
    steps: list[dict[str, Any]] = []
    raw_materials: dict[str, float] = {}
    plan_factory_step(target_item, target_rate, unlocked_schematics, steps, raw_materials)

    # Combine steps by item name and recipe to avoid duplicates in summary
    combined_steps = {}
    for step in steps:
        key = (step["item"], step["recipe_name"])
        if key not in combined_steps:
            combined_steps[key] = {
                "item": step["item"],
                "rate": 0.0,
                "recipe_name": step["recipe_name"],
                "machine": step["machine"],
                "machine_count": 0.0,
                "unlocked": step["unlocked"],
                "alternate": step["alternate"],
            }
        combined_steps[key]["rate"] += step["rate"]
        combined_steps[key]["machine_count"] += step["machine_count"]

    steps_list = list(combined_steps.values())

    # Generate warnings for locked recipes
    for step in steps_list:
        if step["alternate"] and not step["unlocked"]:
            warnings.append(
                f"Alternate Recipe '{step['recipe_name']}' is locked in your save file (requires MAM research)."
            )

    # 4. Calculate miner requirements (overclocked Mk.3 Miner on Pure node = 1200/min)
    miner_requirements = {}
    for raw_item, raw_rate in raw_materials.items():
        # Extractor rates: liquids/gases have different rates than solid ores
        if raw_item in ["Water", "Crude Oil", "Nitrogen Gas"]:
            # Water Extractor at 250% = 300/min
            # Oil Extractor Pure at 250% = 600/min
            # Resource Well Pure at 250% = 600/min
            extractor_capacity = 300.0 if raw_item == "Water" else 600.0
            miner_requirements[raw_item] = {
                "rate": raw_rate,
                "extractors_needed": raw_rate / extractor_capacity,
                "details": f"Pure node / Extractor at 250% (Max {extractor_capacity}/min)",
            }
        else:
            # Solid ores: Mk.3 Miner Pure node at 250% = 1200/min (Mk.6 Belt limit)
            miner_requirements[raw_item] = {
                "rate": raw_rate,
                "extractors_needed": raw_rate / 1200.0,
                "details": "Mk.3 Miner Pure node at 250% (Max 1200/min)",
            }

    return {
        "target_item": target_item,
        "target_rate": target_rate,
        "coupons_per_minute": coupons_per_minute,
        "current_coupons": current_coupons,
        "points_required": points_required,
        "steps": steps_list,
        "raw_materials": raw_materials,
        "miners": miner_requirements,
        "warnings": warnings,
    }


def generate_mermaid_flowchart(
    target_item: str,
    target_rate: float,
) -> str:
    """Generates a Mermaid TD flowchart of the factory production tree."""
    lines = ["flowchart TD"]
    node_id_map = {}
    node_counter = 0
    edges = []

    def get_node_id(item_name: str, recipe_name: str) -> str:
        nonlocal node_counter
        key = (item_name, recipe_name)
        if key not in node_id_map:
            node_counter += 1
            node_id_map[key] = f"node{node_counter}"
        return node_id_map[key]

    def trace(item: str, rate: float, parent_node_id: str | None = None):
        if item not in RECIPES:
            node_id = get_node_id(item, "Raw Extractor")
            label = f'"{item}\\n(Raw Resource)"'
            lines.append(f"    {node_id}[{label}]")
            if parent_node_id:
                edges.append(f'    {node_id} -- "{rate:.2f}/min" --> {parent_node_id}')
            return

        recipe_dict = RECIPES[item]
        recipe = recipe_dict.get("best", recipe_dict["default"])
        recipe_name = recipe["name"]
        machine = recipe["machine"]
        base_output = recipe["outputs"][item]
        machine_count = rate / base_output

        node_id = get_node_id(item, recipe_name)
        label = f'"{machine} x{machine_count:.2f}\\n{recipe_name}\\n({rate:.2f}/min)"'
        lines.append(f"    {node_id}[{label}]")

        if parent_node_id:
            edges.append(f'    {node_id} -- "{rate:.2f}/min" --> {parent_node_id}')

        for input_item, input_rate_per_machine in recipe["inputs"].items():
            required_input_rate = input_rate_per_machine * machine_count
            trace(input_item, required_input_rate, node_id)

    trace(target_item, target_rate)
    lines.extend(edges)
    return "\n".join(lines)
