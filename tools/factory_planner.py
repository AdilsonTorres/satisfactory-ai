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
        # Extra robustness for 1.0 diamond renames
        unlocked = schem_name in unlocked_schematics
        if schem_name == "Schematic_Alternate_Diamond_OilBased":
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
    return_dict: bool = False,
) -> str | dict[str, Any]:
    """Generates a Mermaid TD flowchart of the factory production tree."""
    class Node:
        def __init__(self, node_id: str, label: str, depth: int, cls: str):
            self.node_id = node_id
            self.label = label
            self.depth = depth
            self.cls = cls

    class Edge:
        def __init__(self, from_node: str, to_node: str, label: str):
            self.from_node = from_node
            self.to_node = to_node
            self.label = label

    nodes_list = []
    edges_list = []
    node_counter = 0

    def trace(item: str, rate: float, parent_node_id: str | None = None, depth: int = 0):
        nonlocal node_counter
        node_counter += 1
        node_id = f"node{node_counter}"

        if item not in RECIPES:
            label = f'"{item}<br/>Raw Resource"'
            nodes_list.append(Node(node_id, label, -1, "raw"))
            if parent_node_id:
                edges_list.append(Edge(node_id, parent_node_id, f"|{rate:.2f}/min|"))
            return

        recipe_dict = RECIPES[item]
        recipe = recipe_dict.get("best", recipe_dict["default"])
        recipe_name = recipe["name"]
        machine = recipe["machine"]
        base_output = recipe["outputs"][item]
        machine_count = rate / base_output

        label = f'"{machine} x{machine_count:.2f}<br/>{recipe_name}<br/>{rate:.2f}/min"'

        if depth == 0:
            cls = "target"
        elif machine in ["Smelter", "Foundry", "Refinery"]:
            cls = "smelting"
        elif machine in ["Constructor", "Assembler"]:
            cls = "processing"
        else:
            cls = "manufacturing"

        nodes_list.append(Node(node_id, label, depth, cls))

        if parent_node_id:
            edges_list.append(Edge(node_id, parent_node_id, f"|{rate:.2f}/min|"))

        for input_item, input_rate_per_machine in recipe["inputs"].items():
            required_input_rate = input_rate_per_machine * machine_count
            trace(input_item, required_input_rate, node_id, depth + 1)

    trace(target_item, target_rate)

    _PHASE_NAMES = {
        -1: "Raw Extraction",
        0: "Final Assembly",
        1: "Primary Components",
        2: "Sub-Components",
    }
    _DEFAULT_NAME = "Basic Processing"

    def compile_flowchart(nodes, edges, core_depth=None):
        lines = [
            "flowchart TD",
            "    classDef raw fill:#212529,stroke:#495057,stroke-width:2px,color:#fff;",
            "    classDef smelting fill:#e65100,stroke:#ffb74d,stroke-width:2px,color:#fff;",
            "    classDef processing fill:#0d47a1,stroke:#64b5f6,stroke-width:2px,color:#fff;",
            "    classDef manufacturing fill:#4a148c,stroke:#ba68c8,stroke-width:2px,color:#fff;",
            "    classDef target fill:#ffb300,stroke:#ffe082,stroke-width:3px,color:#000;"
        ]

        grouped = {}
        for n in nodes:
            grouped.setdefault(n.depth, []).append(n)

        for d in sorted(grouped.keys(), key=lambda x: 999 if x == -1 else x, reverse=True):
            if core_depth is not None and d != core_depth:
                for n in grouped[d]:
                    lines.append(f"    {n.node_id}[{n.label}]")
                continue

            phase_name = _PHASE_NAMES.get(d, _DEFAULT_NAME)
            if d >= 3:
                phase_name = f"{phase_name} (Tier {d-2})"
            lines.append(f"    subgraph Phase_{d} [\"{phase_name}\"]")
            for n in grouped[d]:
                lines.append(f"        {n.node_id}[{n.label}]")
            lines.append("    end")

        for e in edges:
            lines.append(f"    {e.from_node} -->{e.label} {e.to_node}")

        for n in nodes:
            lines.append(f"    class {n.node_id} {n.cls};")

        return "\n".join(lines)

    full_chart = compile_flowchart(nodes_list, edges_list)

    if not return_dict:
        return full_chart

    phase_flowcharts = {}
    depths = {n.depth for n in nodes_list if n.depth != -1}
    for d in depths:
        core_node_ids = {n.node_id for n in nodes_list if n.depth == d}
        phase_edges = [
            e for e in edges_list
            if e.from_node in core_node_ids or e.to_node in core_node_ids
        ]
        connected_node_ids = {e.from_node for e in phase_edges} | {e.to_node for e in phase_edges} | core_node_ids
        phase_nodes = [n for n in nodes_list if n.node_id in connected_node_ids]
        phase_flowcharts[str(d)] = compile_flowchart(phase_nodes, phase_edges, core_depth=d)

    return {
        "full": full_chart,
        "phases": phase_flowcharts
    }
