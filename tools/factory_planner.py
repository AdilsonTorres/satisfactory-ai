import math
from typing import Any, cast

from utils.recipe_db import RECIPES, SINK_POINTS
from utils.save_parser import SatisfactorySave


def get_coupon_point_cost(current_coupons: int) -> int:
    """Calculates point cost of the next coupon using the quadratic scaling formula."""
    # Points = 500 * (ceil((n + 1) / 3) - 1)^2 + 1000
    n = current_coupons + 1
    ceil_val = math.ceil(n / 3)
    return 500 * ((ceil_val - 1) ** 2) + 1000


def plan_specific_factory_step(
    item: str,
    rate: float,
    recipe: dict[str, Any],
    unlocked_schematics: set[str],
    steps: list[dict[str, Any]],
    raw_materials: dict[str, float],
    recipe_multiplier: float = 1.0,
) -> Any:
    output_rate = recipe["outputs"][item]
    machine_count = rate / output_rate

    steps.append(
        {
            "item": item,
            "rate": rate,
            "recipe_name": recipe["name"],
            "machine": recipe["machine"],
            "machine_count": machine_count,
            "unlocked": recipe.get("schematic") is None or recipe["schematic"] in unlocked_schematics,
            "alternate": recipe.get("alternate", False),
            "byproducts": {
                out_item: rate * (out_rate / output_rate)
                for out_item, out_rate in recipe["outputs"].items()
                if out_item != item
            },
        }
    )

    for input_item, input_rate_per_machine in recipe["inputs"].items():
        required_input_rate = input_rate_per_machine * recipe_multiplier * machine_count
        if input_item in ["Water", "Dark Matter Residue", "Heavy Oil Residue"]:
            pass  # Do not add to raw_materials since it is satisfied by byproduct overflow
        else:
            plan_factory_step(
                input_item,
                required_input_rate,
                unlocked_schematics,
                steps,
                raw_materials,
                recipe_multiplier=recipe_multiplier,
            )


def plan_factory_step(
    item: str,
    rate: float,
    unlocked_schematics: set[str],
    steps: list[dict[str, Any]],
    raw_materials: dict[str, float],
    terminal_byproducts: set[str] | None = None,
    recipe_multiplier: float = 1.0,
    depth: int = 0,
) -> Any:
    """Recursively traces production tree using the best alternate recipes."""
    # If it is a raw resource (no recipes exist for it), add to raw materials and stop
    if item not in RECIPES or (terminal_byproducts and item in terminal_byproducts):
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

    is_unlocked = recipe.get("schematic") is None or recipe["schematic"] in unlocked_schematics
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
            "byproducts": {
                out_item: rate * (out_rate / output_rate)
                for out_item, out_rate in recipe["outputs"].items()
                if out_item != item
            },
        }
    )

    # Recursively trace inputs
    for input_item, input_rate_per_machine in recipe["inputs"].items():
        required_input_rate = input_rate_per_machine * recipe_multiplier * machine_count
        plan_factory_step(
            input_item,
            required_input_rate,
            unlocked_schematics,
            steps,
            raw_materials,
            terminal_byproducts,
            recipe_multiplier=recipe_multiplier,
            depth=depth + 1,
        )


def generate_production_plan(
    target_item: str | None,
    target_rate: float | None,
    coupons_per_minute: float | None,
    save_file_path: str,
    recipe_multiplier: float = 1.0,
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

    # 3. Recursively generate tree steps with terminal byproducts
    steps: list[dict[str, Any]] = []
    raw_materials: dict[str, float] = {}
    terminal_byproducts = {"Water", "Dark Matter Residue", "Heavy Oil Residue"}

    plan_factory_step(
        target_item,
        target_rate,
        unlocked_schematics,
        steps,
        raw_materials,
        terminal_byproducts=terminal_byproducts,
        recipe_multiplier=recipe_multiplier,
    )

    # Balance byproducts
    for bp in ["Water", "Dark Matter Residue", "Heavy Oil Residue"]:
        consumed = raw_materials.get(bp, 0.0)
        produced = 0.0
        for step in steps:
            bp_rates = step.get("byproducts", {})
            if bp in bp_rates:
                produced += bp_rates[bp]

        net_rate = consumed - produced
        if abs(net_rate) < 1e-4:
            raw_materials.pop(bp, None)
            continue

        if net_rate > 0:
            raw_materials.pop(bp, None)
            plan_factory_step(
                bp,
                net_rate,
                unlocked_schematics,
                steps,
                raw_materials,
                terminal_byproducts=None,
                recipe_multiplier=recipe_multiplier,
            )
        else:
            raw_materials.pop(bp, None)
            overflow_rate = -net_rate

            if bp == "Water":
                disp_item = "Concrete"
                recipe = RECIPES[disp_item]["best"]  # Wet Concrete
                concrete_rate = overflow_rate * recipe["outputs"][disp_item] / recipe["inputs"][bp]
                plan_specific_factory_step(
                    disp_item,
                    concrete_rate,
                    recipe,
                    unlocked_schematics,
                    steps,
                    raw_materials,
                    recipe_multiplier=recipe_multiplier,
                )
            elif bp == "Dark Matter Residue":
                disp_item = "Dark Matter Crystal"
                recipe_dict = RECIPES[disp_item]
                best = recipe_dict.get("best")
                default = recipe_dict["default"]
                if (
                    best
                    and best.get("alternate")
                    and best.get("schematic")
                    and best["schematic"] in unlocked_schematics
                ):
                    recipe = best
                else:
                    recipe = default
                crystal_rate = overflow_rate * recipe["outputs"][disp_item] / recipe["inputs"][bp]
                plan_specific_factory_step(
                    disp_item,
                    crystal_rate,
                    recipe,
                    unlocked_schematics,
                    steps,
                    raw_materials,
                    recipe_multiplier=recipe_multiplier,
                )
            elif bp == "Heavy Oil Residue":
                disp_item = "Petroleum Coke"
                recipe = RECIPES[disp_item]["default"]
                coke_rate = overflow_rate * recipe["outputs"][disp_item] / recipe["inputs"][bp]
                plan_specific_factory_step(
                    disp_item,
                    coke_rate,
                    recipe,
                    unlocked_schematics,
                    steps,
                    raw_materials,
                    recipe_multiplier=recipe_multiplier,
                )

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
        "unlocked_schematics": list(unlocked_schematics),
    }


def generate_mermaid_flowchart(
    target_item: str,
    target_rate: float,
    unlocked_schematics: set[str] | None = None,
    return_dict: bool = False,
    recipe_multiplier: float = 1.0,
) -> str | dict[str, Any]:
    """Generates a Mermaid TD flowchart of the factory production tree."""

    class Node:
        def __init__(self, node_id: str, label: str, depth: int, cls: str) -> None:
            self.node_id = node_id
            self.label = label
            self.depth = depth
            self.cls = cls

    class Edge:
        def __init__(self, from_node: str, to_node: str, label: str) -> None:
            self.from_node = from_node
            self.to_node = to_node
            self.label = label

    nodes_list = []
    edges_list = []
    node_counter = 0

    if unlocked_schematics is None:
        unlocked_schematics = set()

    terminal_byproducts = {"Water", "Dark Matter Residue", "Heavy Oil Residue"}
    byproduct_records = []
    byproduct_raw_needs: dict[str, float] = {}

    def trace_specific(item: str, rate: float, recipe: dict[str, Any], depth: int = 1) -> Any:
        nonlocal node_counter
        node_counter += 1
        node_id = f"node{node_counter}"

        recipe_name = recipe["name"]
        machine = recipe["machine"]
        base_output = recipe["outputs"][item]
        machine_count = rate / base_output

        label = f'"{machine} x{machine_count:.2f}<br/>{recipe_name}<br/>{rate:.2f}/min"'

        if machine in ["Smelter", "Foundry", "Refinery"]:
            cls = "smelting"
        elif machine in ["Constructor", "Assembler"]:
            cls = "processing"
        else:
            cls = "manufacturing"

        nodes_list.append(Node(node_id, label, depth, cls))

        # Recurse through inputs
        for input_item, input_rate_per_machine in recipe["inputs"].items():
            required_input_rate = input_rate_per_machine * recipe_multiplier * machine_count
            if input_item in terminal_byproducts:
                pass  # Do not draw a raw resource node for the byproduct input of the disposal step
            else:
                trace(input_item, required_input_rate, node_id, depth + 1)

    def trace(item: str, rate: float, parent_node_id: str | None = None, depth: int = 0) -> Any:
        nonlocal node_counter
        node_counter += 1
        node_id = f"node{node_counter}"

        if item in terminal_byproducts:
            byproduct_raw_needs[item] = byproduct_raw_needs.get(item, 0.0) + rate
            label = f'"<b>{item}</b><br/>Raw Resource<br/><b>{rate:.2f}/min</b>"'
            nodes_list.append(Node(node_id, label, -1, "raw"))
            if parent_node_id:
                edges_list.append(Edge(node_id, parent_node_id, f"|{rate:.2f}/min|"))
            return

        if item not in RECIPES:
            label = f'"<b>{item}</b><br/>Raw Resource<br/><b>{rate:.2f}/min</b>"'
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

        # Track byproducts
        for out_item, out_rate in recipe["outputs"].items():
            if out_item != item and out_item in terminal_byproducts:
                bp_rate = rate * (out_rate / base_output)
                byproduct_records.append({"item": out_item, "rate": bp_rate, "depth": depth})

        label = f'"<b>{item}</b><br/>{machine} x{machine_count:.2f}<br/><i>{recipe_name}</i><br/><b>{rate:.2f}/min</b>"'

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
            required_input_rate = input_rate_per_machine * recipe_multiplier * machine_count
            trace(input_item, required_input_rate, node_id, depth + 1)

    trace(target_item, target_rate)

    # Balance byproducts for flowchart
    for bp in terminal_byproducts:
        consumed = byproduct_raw_needs.get(bp, 0.0)
        produced = sum(r["rate"] for r in byproduct_records if r["item"] == bp)
        byproduct_depths = [r["depth"] for r in byproduct_records if r["item"] == bp]
        net_rate = consumed - produced

        if abs(net_rate) < 1e-4:
            continue

        if net_rate > 0:
            disp_depth = min(byproduct_depths) if byproduct_depths else 1
            trace(bp, net_rate, depth=disp_depth)
        else:
            overflow_rate = -net_rate
            disp_depth = min(byproduct_depths) if byproduct_depths else 1

            if bp == "Water":
                disp_item = "Concrete"
                recipe = RECIPES[disp_item]["best"]
                concrete_rate = overflow_rate * recipe["outputs"][disp_item] / recipe["inputs"][bp]
                trace_specific(disp_item, concrete_rate, recipe, depth=disp_depth)
            elif bp == "Dark Matter Residue":
                disp_item = "Dark Matter Crystal"
                recipe_dict = RECIPES[disp_item]
                best = recipe_dict.get("best")
                default = recipe_dict["default"]
                if (
                    best
                    and best.get("alternate")
                    and best.get("schematic")
                    and best["schematic"] in unlocked_schematics
                ):
                    recipe = best
                else:
                    recipe = default
                crystal_rate = overflow_rate * recipe["outputs"][disp_item] / recipe["inputs"][bp]
                trace_specific(disp_item, crystal_rate, recipe, depth=disp_depth)
            elif bp == "Heavy Oil Residue":
                disp_item = "Petroleum Coke"
                recipe = RECIPES[disp_item]["default"]
                coke_rate = overflow_rate * recipe["outputs"][disp_item] / recipe["inputs"][bp]
                trace_specific(disp_item, coke_rate, recipe, depth=disp_depth)

    _PHASE_NAMES = {
        -1: "Raw Extraction",
        0: "Final Assembly",
        1: "Primary Components",
        2: "Sub-Components",
    }
    _DEFAULT_NAME = "Basic Processing"

    def compile_flowchart(nodes: Any, edges: Any, core_depth: Any = None) -> Any:
        lines = [
            "flowchart TD",
            "    classDef raw fill:#212529,stroke:#495057,stroke-width:2px,color:#fff;",
            "    classDef smelting fill:#e65100,stroke:#ffb74d,stroke-width:2px,color:#fff;",
            "    classDef processing fill:#0d47a1,stroke:#64b5f6,stroke-width:2px,color:#fff;",
            "    classDef manufacturing fill:#4a148c,stroke:#ba68c8,stroke-width:2px,color:#fff;",
            "    classDef target fill:#ffb300,stroke:#ffe082,stroke-width:3px,color:#000;",
        ]

        grouped: dict[int, list[Any]] = {}
        for n in nodes:
            grouped.setdefault(n.depth, []).append(n)

        for d in sorted(grouped.keys(), key=lambda x: 999 if x == -1 else x, reverse=True):
            if core_depth is not None and d != core_depth:
                for n in grouped[d]:
                    lines.append(f"    {n.node_id}[{n.label}]")
                continue

            phase_name = _PHASE_NAMES.get(d, _DEFAULT_NAME)
            if d >= 3:
                phase_name = f"{phase_name} (Tier {d - 2})"
            lines.append(f'    subgraph Phase_{d} ["{phase_name}"]')
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
        return cast(str, full_chart)

    phase_flowcharts = {}
    depths = {n.depth for n in nodes_list if n.depth != -1}
    for d in depths:
        core_node_ids = {n.node_id for n in nodes_list if n.depth == d}
        phase_edges = [e for e in edges_list if e.from_node in core_node_ids or e.to_node in core_node_ids]
        connected_node_ids = {e.from_node for e in phase_edges} | {e.to_node for e in phase_edges} | core_node_ids
        phase_nodes = [n for n in nodes_list if n.node_id in connected_node_ids]
        phase_flowcharts[str(d)] = compile_flowchart(phase_nodes, phase_edges, core_depth=d)

    return cast(dict[str, Any], {"full": full_chart, "phases": phase_flowcharts})
