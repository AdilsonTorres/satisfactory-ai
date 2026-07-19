import difflib
import math
import re
from typing import Any, cast

from utils.recipe_db import RECIPES
from utils.save_parser import SatisfactorySave

# Supplement RECIPES with 1.2+ quantum items (base rates per minute at 100%)
EXTRAS = {
    "Automated Wiring": {
        "best": {
            "name": "Automated Wiring",
            "machine": "Assembler",
            "inputs": {"Stator": 2.5, "Cable": 50.0},
            "outputs": {"Automated Wiring": 2.5},
            "alternate": False,
        }
    },
    "Ficsite Trigon": {
        "best": {
            "name": "Ficsite Trigon",
            "machine": "Constructor",
            "inputs": {"Ficsite Ingot": 30.0},
            "outputs": {"Ficsite Trigon": 90.0},
            "alternate": False,
        }
    },
    "Ficsite Ingot": {
        "best": {
            "name": "Ficsite Ingot (Aluminum)",
            "machine": "Converter",
            "inputs": {"Reanimated SAM": 60.0, "Aluminum Ingot": 120.0},
            "outputs": {"Ficsite Ingot": 30.0},
            "alternate": False,
        }
    },
    "Reanimated SAM": {
        "best": {
            "name": "Reanimated SAM",
            "machine": "Constructor",
            "inputs": {"SAM": 120.0},
            "outputs": {"Reanimated SAM": 30.0},
            "alternate": False,
        }
    },
    "Time Crystal": {
        "best": {
            "name": "Time Crystal",
            "machine": "Converter",
            "inputs": {"Diamond": 12.0},
            "outputs": {"Time Crystal": 6.0},
            "alternate": False,
        }
    },
    "Dark Matter Residue": {
        "best": {
            "name": "Dark Matter Residue",
            "machine": "Converter",
            "inputs": {"Reanimated SAM": 50.0},
            "outputs": {"Dark Matter Residue": 100.0},
            "alternate": False,
        }
    },
    "Excited Photonic Matter": {
        "best": {
            "name": "Excited Photonic Matter",
            "machine": "Converter",
            "inputs": {},
            "outputs": {"Excited Photonic Matter": 200.0},
            "alternate": False,
        }
    },
}

ALL_RECIPES = {**RECIPES, **EXTRAS}

# Base power consumption of production machines in MW
MACHINE_BASE_POWER = {
    "Smelter": 4.0,
    "Constructor": 4.0,
    "Foundry": 16.0,
    "Refinery": 30.0,
    "Assembler": 15.0,
    "Blender": 75.0,
    "Manufacturer": 55.0,
    "Particle Accelerator": 1000.0,
    "Quantum Encoder": 1000.0,
    "Converter": 250.0,
}

# Somersloop slots per machine
MACHINE_SLOOPS = {
    "Smelter": 1,
    "Constructor": 1,
    "Foundry": 2,
    "Refinery": 2,
    "Assembler": 2,
    "Blender": 4,
    "Manufacturer": 4,
    "Particle Accelerator": 4,
    "Quantum Encoder": 4,
    "Converter": 2,
}

ITEM_MAP = {
    "Desc_SteelPipe": "Steel Pipe",
    "Desc_Motor": "Motor",
    "Desc_Cable": "Cable",
    "Desc_Cement": "Concrete",
    "Desc_CircuitBoard": "Circuit Board",
    "Desc_ModularFrame": "Modular Frame",
    "Desc_IronScrew": "Screw",
    "Desc_IronRod": "Iron Rod",
    "Desc_IronPlate": "Iron Plate",
    "Desc_QuartzCrystal": "Quartz Crystal",
    "Desc_HighSpeedConnector": "High-Speed Connector",
    "Desc_HighSpeedWire": "Quickwire",
    "Desc_AluminumPlate": "Alclad Aluminum Sheet",
    "Desc_AluminumPlateReinforced": "Aluminum Casing",
    "Desc_SAM": "SAM",
    "Desc_Silicon": "Silica",
    "Desc_QuantumOscillator": "Superposition Oscillator",
    "Desc_SingularityCell": "Singularity Cell",
    "Desc_DarkMatterCrystal": "Dark Matter Crystal",
    "Desc_NeuralQuantumProcessor": "Neural-Quantum Processor",
    "Desc_SpaceElevatorPart9": "Ballistic Warp Drive",
    "Desc_SpaceElevatorPart10": "AI Expansion Server",
    "Desc_SpaceElevatorPart11": "Biochemical Sculptor",
    "Desc_NuclearPasta": "Nuclear Pasta",
    "Desc_SpaceElevatorPart8": "Assembly Director System",
    "Desc_SpaceElevatorPart7": "Thermal Propulsion Rocket",
    "Desc_SpaceElevatorPart6": "Magnetic Field Generator",
    "Desc_ModularEngine": "Modular Engine",
    "Desc_SpaceElevatorPart5": "Adaptive Control Unit",
    "Desc_CrystalOscillator": "Crystal Oscillator",
    "Desc_ElectromagneticControlRod": "Electromagnetic Control Rod",
    "Desc_UraniumCell": "Encased Uranium Cell",
    "Desc_UraniumFuelRod": "Uranium Fuel Rod",
    "Desc_SpaceElevatorPart4": "Versatile Framework",
    "Desc_SpaceElevatorPart3": "Automated Wiring",
    "Desc_SpaceElevatorPart2": "Smart Plating",
    "Desc_EnrichedCoal": "Compacted Coal",
    "Desc_Rubber": "Rubber",
    "Desc_Plastic": "Plastic",
    "Desc_HeavyOilResidue": "Heavy Oil Residue",
    "Desc_AluminumIngot": "Aluminum Ingot",
    "Desc_AluminumScrap": "Aluminum Scrap",
    "Desc_AluminaSolution": "Alumina Solution",
    "Desc_Wire": "Wire",
    "Desc_CateriumIngot": "Caterium Ingot",
    "Desc_CopperIngot": "Copper Ingot",
    "Desc_IronIngot": "Iron Ingot",
    "Desc_SteelIngot": "Steel Ingot",
    "Desc_CopperSheet": "Copper Sheet",
    "Desc_Stator": "Stator",
    "Desc_Rotor": "Rotor",
    "Desc_Fuel": "Fuel",
}


def get_readable_name(class_name: str) -> str:
    if class_name in ITEM_MAP:
        return ITEM_MAP[class_name]
    name = class_name.replace("Desc_", "")
    name = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
    return name


def validate_item_name(item: str, valid_items: set[str], label: str = "Item") -> None:
    """Validate that *item* exists in *valid_items*.

    Raises ``ValueError`` with up to 5 fuzzy suggestions when the name is
    not found.
    """
    if item in valid_items:
        return
    suggestions = difflib.get_close_matches(item, valid_items, n=5, cutoff=0.45)
    msg = f"{label} '{item}' is not recognised in the recipe database."
    if suggestions:
        formatted = ", ".join(f"'{s}'" for s in suggestions)
        msg += f" Did you mean: {formatted}?"
    raise ValueError(msg)


def plan_specific_step(
    item: str,
    rate: float,
    recipe: dict[str, Any],
    unlocked_schematics: set[str],
    sloop_items: set[str],
    overclock: bool,
    recipe_multiplier: float,
    steps: list[dict[str, Any]],
    raw_materials: dict[str, float],
    depth: int,
):
    base_output = recipe["outputs"][item]
    machine_name = recipe["machine"]

    is_slopped = item in sloop_items
    sloop_mult = 2.0 if is_slopped else 1.0
    sloop_slots = MACHINE_SLOOPS.get(machine_name, 0) if is_slopped else 0
    speed_mult = 2.5 if overclock else 1.0

    output_per_machine = base_output * sloop_mult * speed_mult
    machine_count = rate / output_per_machine

    overclock_power_factor = (speed_mult**1.321928) if overclock else 1.0
    sloop_power_factor = 4.0 if is_slopped else 1.0
    base_mw = MACHINE_BASE_POWER.get(machine_name, 10.0)
    power_per_machine = base_mw * overclock_power_factor * sloop_power_factor
    total_mw = power_per_machine * machine_count

    shards_used = 3 if overclock else 0
    sloops_used = sloop_slots

    steps.append(
        {
            "item": item,
            "rate": rate,
            "recipe_name": recipe["name"],
            "machine": machine_name,
            "machine_count": machine_count,
            "unlocked": recipe.get("schematic") is None or recipe["schematic"] in unlocked_schematics,
            "alternate": recipe.get("alternate", False),
            "is_slopped": is_slopped,
            "shards": shards_used,
            "sloops": sloops_used,
            "power_mw": total_mw,
            "output_per_machine": output_per_machine,
            "depth": depth,
            "byproducts": {out_item: rate * (out_rate / base_output) for out_item, out_rate in recipe["outputs"].items() if out_item != item}
        }
    )

    for input_item, input_rate_per_machine in recipe["inputs"].items():
        required_input_rate = input_rate_per_machine * recipe_multiplier * (rate / (base_output * sloop_mult))
        if input_item in ["Water", "Dark Matter Residue", "Heavy Oil Residue"]:
            pass  # Do not add to raw_materials since it is satisfied by byproduct overflow
        else:
            plan_step(
                input_item,
                required_input_rate,
                unlocked_schematics,
                sloop_items,
                overclock,
                recipe_multiplier,
                steps,
                raw_materials,
                depth=depth + 1,
            )


def plan_step(
    item: str,
    rate: float,
    unlocked_schematics: set[str],
    sloop_items: set[str],
    overclock: bool,
    recipe_multiplier: float,
    steps: list[dict[str, Any]],
    raw_materials: dict[str, float],
    depth: int = 0,
    terminal_byproducts: set[str] = None,
):
    if item not in ALL_RECIPES or (terminal_byproducts and item in terminal_byproducts):
        raw_materials[item] = raw_materials.get(item, 0.0) + rate
        return

    recipe_dict = ALL_RECIPES[item]
    best = recipe_dict.get("best")
    default = recipe_dict.get("default")

    # Use best recipe only if it is unlocked; fall back to default silently.
    # Some late-game items (Ficsite Trigon, etc.) have no default — always use best.
    if best and best.get("alternate") and best.get("schematic") and default:
        recipe: dict[str, Any] = best if best["schematic"] in unlocked_schematics else default
    elif best is not None:
        recipe = best
    else:
        recipe = cast(dict[str, Any], default)
    assert recipe is not None  # every item in ALL_RECIPES has at least a best or default

    is_unlocked = recipe.get("schematic") is None or recipe["schematic"] in unlocked_schematics

    base_output = recipe["outputs"][item]
    machine_name = recipe["machine"]

    # Somersloop check
    is_slopped = item in sloop_items
    sloop_mult = 2.0 if is_slopped else 1.0
    sloop_slots = MACHINE_SLOOPS.get(machine_name, 0) if is_slopped else 0

    # Overclock speed check (250% = 2.5x speed)
    speed_mult = 2.5 if overclock else 1.0

    # Required output per single machine
    output_per_machine = base_output * sloop_mult * speed_mult
    machine_count = rate / output_per_machine

    # Power calculations
    overclock_power_factor = (speed_mult**1.321928) if overclock else 1.0
    sloop_power_factor = 4.0 if is_slopped else 1.0

    base_mw = MACHINE_BASE_POWER.get(machine_name, 10.0)
    power_per_machine = base_mw * overclock_power_factor * sloop_power_factor
    total_mw = power_per_machine * machine_count

    shards_used = 3 if overclock else 0
    sloops_used = sloop_slots

    steps.append(
        {
            "item": item,
            "rate": rate,
            "recipe_name": recipe["name"],
            "machine": machine_name,
            "machine_count": machine_count,
            "unlocked": is_unlocked,
            "alternate": recipe.get("alternate", False),
            "is_slopped": is_slopped,
            "shards": shards_used,
            "sloops": sloops_used,
            "power_mw": total_mw,
            "output_per_machine": output_per_machine,
            "depth": depth,
            "byproducts": {out_item: rate * (out_rate / base_output) for out_item, out_rate in recipe["outputs"].items() if out_item != item}
        }
    )

    # Recurse through inputs
    for input_item, input_rate_per_machine in recipe["inputs"].items():
        # Apply the recipe cost multiplier to raw inputs
        required_input_rate = input_rate_per_machine * recipe_multiplier * (rate / (base_output * sloop_mult))
        plan_step(
            input_item,
            required_input_rate,
            unlocked_schematics,
            sloop_items,
            overclock,
            recipe_multiplier,
            steps,
            raw_materials,
            depth=depth + 1,
            terminal_byproducts=terminal_byproducts,
        )


def generate_late_game_plan(
    target_item: str,
    target_rate: float,
    overclock: bool,
    sloop_items: set[str],
    save_file_path: str,
    recipe_multiplier: float = 1.0,
) -> dict[str, Any]:
    # Validate item names before doing any heavy work
    valid_items = set(ALL_RECIPES.keys())
    validate_item_name(target_item, valid_items, label="Target item")
    for sloop_item in sloop_items:
        validate_item_name(sloop_item, valid_items, label="Somersloop item")

    save = SatisfactorySave(save_file_path)
    # mPurchasedSchematics (milestones) + mAvailableRecipes (MAM hard-drive unlocks).
    # mAvailableRecipes uses "Recipe_Alternate_X"; recipe_db keys use "Schematic_Alternate_X".
    unlocked_schematics = set(save.schematics) | {
        r.replace("Recipe_Alternate_", "Schematic_Alternate_", 1)
        for r in save.recipes
        if r.startswith("Recipe_Alternate_")
    }

    steps: list[dict[str, Any]] = []
    raw_materials: dict[str, float] = {}
    terminal_byproducts = {"Water", "Dark Matter Residue", "Heavy Oil Residue"}

    plan_step(
        target_item, target_rate, unlocked_schematics, sloop_items, overclock, recipe_multiplier, steps, raw_materials,
        terminal_byproducts=terminal_byproducts
    )

    # Balance byproducts
    for bp in ["Water", "Dark Matter Residue", "Heavy Oil Residue"]:
        consumed = raw_materials.get(bp, 0.0)
        produced = 0.0
        byproduct_depths = []
        for step in steps:
            bp_rates = step.get("byproducts", {})
            if bp in bp_rates:
                produced += bp_rates[bp]
                byproduct_depths.append(step.get("depth", 0))

        net_rate = consumed - produced
        if abs(net_rate) < 1e-4:
            if bp in raw_materials:
                del raw_materials[bp]
            continue

        if net_rate > 0:
            if bp in raw_materials:
                del raw_materials[bp]
            plan_step(
                bp, net_rate, unlocked_schematics, sloop_items, overclock, recipe_multiplier,
                steps, raw_materials, depth=min(byproduct_depths) if byproduct_depths else 1,
                terminal_byproducts=None
            )
        else:
            if bp in raw_materials:
                del raw_materials[bp]
            overflow_rate = -net_rate
            disp_depth = min(byproduct_depths) if byproduct_depths else 1

            if bp == "Water":
                disp_item = "Concrete"
                recipe = ALL_RECIPES[disp_item]["best"]  # Wet Concrete
                is_slopped = disp_item in sloop_items
                sloop_mult = 2.0 if is_slopped else 1.0
                concrete_rate = overflow_rate * (recipe["outputs"][disp_item] * sloop_mult) / recipe["inputs"][bp]
                plan_specific_step(
                    disp_item, concrete_rate, recipe, unlocked_schematics, sloop_items, overclock, recipe_multiplier,
                    steps, raw_materials, depth=disp_depth
                )
            elif bp == "Dark Matter Residue":
                disp_item = "Dark Matter Crystal"
                recipe_dict = ALL_RECIPES[disp_item]
                best = recipe_dict.get("best")
                default = recipe_dict["default"]
                if best and best.get("alternate") and best.get("schematic") and best["schematic"] in unlocked_schematics:
                    recipe = best
                else:
                    recipe = default
                is_slopped = disp_item in sloop_items
                sloop_mult = 2.0 if is_slopped else 1.0
                crystal_rate = overflow_rate * (recipe["outputs"][disp_item] * sloop_mult) / recipe["inputs"][bp]
                plan_specific_step(
                    disp_item, crystal_rate, recipe, unlocked_schematics, sloop_items, overclock, recipe_multiplier,
                    steps, raw_materials, depth=disp_depth
                )
            elif bp == "Heavy Oil Residue":
                disp_item = "Petroleum Coke"
                recipe = ALL_RECIPES[disp_item]["default"]
                is_slopped = disp_item in sloop_items
                sloop_mult = 2.0 if is_slopped else 1.0
                coke_rate = overflow_rate * (recipe["outputs"][disp_item] * sloop_mult) / recipe["inputs"][bp]
                plan_specific_step(
                    disp_item, coke_rate, recipe, unlocked_schematics, sloop_items, overclock, recipe_multiplier,
                    steps, raw_materials, depth=disp_depth
                )

    # Combine steps
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
                "is_slopped": step["is_slopped"],
                "shards_per_machine": step["shards"],
                "sloops_per_machine": step["sloops"],
                "power_mw": 0.0,
                "output_per_machine": step["output_per_machine"],
                "depth": step["depth"],
            }
        combined_steps[key]["rate"] += step["rate"]
        combined_steps[key]["machine_count"] += step["machine_count"]
        combined_steps[key]["power_mw"] += step["power_mw"]
        combined_steps[key]["depth"] = min(combined_steps[key]["depth"], step["depth"])

    steps_list = list(combined_steps.values())

    # Calculate resources & machines sums
    total_shards = 0
    total_sloops = 0
    total_power = 0.0
    warnings: list[str] = []

    for step in steps_list:
        actual_machines = math.ceil(step["machine_count"])
        total_shards += actual_machines * step["shards_per_machine"]
        total_sloops += actual_machines * step["sloops_per_machine"]
        total_power += step["power_mw"]
        if not step["unlocked"]:
            warnings.append(f"Recipe '{step['recipe_name']}' is locked in your save file (needs to be unlocked).")

    # Read Dimensional Depot quantities
    depot_status = {}
    for entry in save.dimensional_depot:
        clean = get_readable_name(entry["name"])
        depot_status[clean] = entry["quantity"]

    # Compare planned items with dimensional depot
    depot_comparison = {}
    for raw, req_rate in raw_materials.items():
        depot_comparison[raw] = {"required_rate": req_rate, "stored_qty": depot_status.get(raw, 0)}

    # Fuel generator calculations (Rocket fuel: 250MW standard, 625MW overclocked)
    generators_needed = total_power / 625.0 if overclock else total_power / 250.0
    rocket_fuel_rate = 10.425 if overclock else 4.17
    total_rocket_fuel_needed = generators_needed * rocket_fuel_rate

    ionized_fuel_rate = 7.5 if overclock else 3.0
    total_ionized_fuel_needed = generators_needed * ionized_fuel_rate

    # Build guide
    build_guide = _compute_build_guide(steps_list, raw_materials)

    return {
        "target_item": target_item,
        "target_rate": target_rate,
        "overclock": overclock,
        "sloop_items": sloop_items,
        "steps": steps_list,
        "raw_materials": raw_materials,
        "total_shards": total_shards,
        "total_sloops": total_sloops,
        "total_power_mw": total_power,
        "warnings": warnings,
        "depot_comparison": depot_comparison,
        "fuel_generators": {
            "generators_needed": generators_needed,
            "rocket_fuel_m3_min": total_rocket_fuel_needed,
            "ionized_fuel_m3_min": total_ionized_fuel_needed,
        },
        "build_guide": build_guide,
        "unlocked_schematics": list(unlocked_schematics),
    }


def _compute_build_guide(
    steps_list: list[dict[str, Any]],
    raw_materials: dict[str, float],
) -> dict[str, Any]:
    """Compute a phased build guide with layout recommendations.

    Returns phases (grouped by dependency depth), inline/dedicated factory
    recommendations, and co-location suggestions.
    """
    # --- Phase grouping by depth ---
    _PHASE_LABELS = {
        0: ("Final Assembly", "End-product machines — your main production line."),
        1: ("Primary Components", "Direct inputs to the final product. Build nearby or use short belts."),
        2: ("Sub-Components", "Intermediate processing feeding into primary components."),
    }
    _DEFAULT_LABEL = (
        "Basic Processing",
        "Foundational material processing. Can be in a separate factory with transport.",
    )

    depth_groups: dict[int, list[dict[str, Any]]] = {}
    for step in steps_list:
        d = step["depth"]
        depth_groups.setdefault(d, []).append(step)

    phases: list[dict[str, Any]] = []
    for d in sorted(depth_groups):
        label, desc = _PHASE_LABELS.get(d, _DEFAULT_LABEL)
        items = sorted(depth_groups[d], key=lambda s: s["item"])
        phases.append(
            {
                "phase": d + 1,
                "name": label,
                "description": desc,
                "depth": d,
                "items": [
                    {
                        "item": s["item"],
                        "machine": s["machine"],
                        "machine_count": math.ceil(s["machine_count"]),
                        "rate": s["rate"],
                        "max_output": math.ceil(s["machine_count"]) * s["output_per_machine"],
                    }
                    for s in items
                ],
            }
        )

    # Add raw extraction phase
    if raw_materials:
        phases.append(
            {
                "phase": len(phases) + 1,
                "name": "Raw Extraction",
                "description": "Mine or extract from resource nodes and transport to processing.",
                "depth": -1,
                "items": [
                    {"item": raw, "machine": "Miner / Extractor", "machine_count": 0, "rate": rate, "max_output": rate}
                    for raw, rate in sorted(raw_materials.items())
                ],
            }
        )

    # --- Consumer analysis for layout recommendations ---
    produced_items = {s["item"] for s in steps_list}
    consumers: dict[str, set[str]] = {}  # item -> set of items that consume it
    for step in steps_list:
        recipe_data = ALL_RECIPES.get(step["item"])
        if recipe_data:
            recipe = recipe_data.get("best") or recipe_data.get("default")
            if recipe:
                for input_item in recipe["inputs"]:
                    consumers.setdefault(input_item, set()).add(step["item"])

    inline_items: list[dict[str, str]] = []
    dedicated_items: list[dict[str, Any]] = []
    for item_name in sorted(consumers):
        item_consumers = consumers[item_name]
        # Only recommend for items we actually produce (not raw materials)
        if item_name not in produced_items:
            continue
        if len(item_consumers) == 1:
            inline_items.append(
                {
                    "item": item_name,
                    "consumer": next(iter(item_consumers)),
                    "recommendation": f"Build in-line — only feeds {next(iter(item_consumers))}.",
                }
            )
        else:
            dedicated_items.append(
                {
                    "item": item_name,
                    "consumers": sorted(item_consumers),
                    "recommendation": f"Dedicated factory — feeds {', '.join(sorted(item_consumers))}.",
                }
            )

    # --- Co-location: items sharing a common input at the same depth ---
    item_depth = {s["item"]: s["depth"] for s in steps_list}
    co_location_groups: list[dict[str, Any]] = []
    seen_groups: set[tuple[str, ...]] = set()

    for shared_input, input_consumers in consumers.items():
        if len(input_consumers) < 2:
            continue
        # Group consumers at the same depth
        by_depth: dict[int, list[str]] = {}
        for c in input_consumers:
            if c in item_depth:
                by_depth.setdefault(item_depth[c], []).append(c)
        for _d, group in by_depth.items():
            if len(group) < 2:
                continue
            key = tuple(sorted(group))
            if key in seen_groups:
                continue
            seen_groups.add(key)
            co_location_groups.append(
                {
                    "items": sorted(group),
                    "shared_input": shared_input,
                    "reason": f"Both consume {shared_input} — co-locate to share supply.",
                }
            )

    return {
        "phases": phases,
        "inline_items": inline_items,
        "dedicated_items": dedicated_items,
        "co_location_groups": co_location_groups,
    }


def generate_mermaid_flowchart(
    target_item: str,
    target_rate: float,
    unlocked_schematics: set[str],
    sloop_items: set[str],
    overclock: bool,
    recipe_multiplier: float = 1.0,
    return_dict: bool = False,
) -> str | dict[str, Any]:
    """Generates a Mermaid TD flowchart of the late-game factory production tree."""

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

    terminal_byproducts = {"Water", "Dark Matter Residue", "Heavy Oil Residue"}
    byproduct_records = []
    byproduct_raw_needs = {}

    def trace_specific(item: str, rate: float, recipe: dict[str, Any], depth: int = 1):
        nonlocal node_counter
        node_counter += 1
        node_id = f"node{node_counter}"

        base_output = recipe["outputs"][item]
        is_slopped = item in sloop_items
        sloop_mult = 2.0 if is_slopped else 1.0
        speed_mult = 2.5 if overclock else 1.0
        output_per_machine = base_output * sloop_mult * speed_mult
        machine_count = rate / output_per_machine

        sloop_suffix = " - Sloop 2x" if is_slopped else ""
        overclock_suffix = " - 250 Overclock" if overclock else ""
        label = f'"{recipe["machine"]} x{machine_count:.2f}<br/>{recipe["name"]}{sloop_suffix}{overclock_suffix}<br/>{rate:.2f}/min"'

        if recipe["machine"] in ["Smelter", "Foundry", "Refinery"]:
            cls = "smelting"
        elif recipe["machine"] in ["Constructor", "Assembler"]:
            cls = "processing"
        else:
            cls = "manufacturing"

        nodes_list.append(Node(node_id, label, depth, cls))

        # Recurse through inputs
        for input_item, input_rate_per_machine in recipe["inputs"].items():
            required_input_rate = input_rate_per_machine * recipe_multiplier * (rate / (base_output * sloop_mult))
            if input_item in terminal_byproducts:
                pass  # Do not draw a raw resource node for the byproduct input of the disposal step
            else:
                trace(input_item, required_input_rate, node_id, depth + 1)

    def trace(item: str, rate: float, parent_node_id: str | None = None, depth: int = 0):
        nonlocal node_counter
        node_counter += 1
        node_id = f"node{node_counter}"

        if item in terminal_byproducts:
            byproduct_raw_needs[item] = byproduct_raw_needs.get(item, 0.0) + rate
            label = f'"{item}<br/>Raw Resource"'
            nodes_list.append(Node(node_id, label, -1, "raw"))
            if parent_node_id:
                edges_list.append(Edge(node_id, parent_node_id, f"|{rate:.2f}/min|"))
            return

        if item not in ALL_RECIPES:
            label = f'"{item}<br/>Raw Resource"'
            nodes_list.append(Node(node_id, label, -1, "raw"))
            if parent_node_id:
                edges_list.append(Edge(node_id, parent_node_id, f"|{rate:.2f}/min|"))
            return

        recipe_dict = ALL_RECIPES[item]
        recipe = recipe_dict.get("best") or recipe_dict["default"]
        recipe_name = recipe["name"]
        machine = recipe["machine"]
        base_output = recipe["outputs"][item]

        is_slopped = item in sloop_items
        sloop_mult = 2.0 if is_slopped else 1.0
        speed_mult = 2.5 if overclock else 1.0

        output_per_machine = base_output * sloop_mult * speed_mult
        machine_count = rate / output_per_machine

        # Track byproducts
        for out_item, out_rate in recipe["outputs"].items():
            if out_item != item and out_item in terminal_byproducts:
                bp_rate = rate * (out_rate / base_output)
                byproduct_records.append({"item": out_item, "rate": bp_rate, "depth": depth})

        sloop_suffix = " - Sloop 2x" if is_slopped else ""
        overclock_suffix = " - 250 Overclock" if overclock else ""
        label = f'"{machine} x{machine_count:.2f}<br/>{recipe_name}{sloop_suffix}{overclock_suffix}<br/>{rate:.2f}/min"'

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
            required_input_rate = input_rate_per_machine * recipe_multiplier * (rate / (base_output * sloop_mult))
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
                recipe = ALL_RECIPES[disp_item]["best"]
                is_slopped = disp_item in sloop_items
                sloop_mult = 2.0 if is_slopped else 1.0
                concrete_rate = overflow_rate * (recipe["outputs"][disp_item] * sloop_mult) / recipe["inputs"][bp]
                trace_specific(disp_item, concrete_rate, recipe, depth=disp_depth)
            elif bp == "Dark Matter Residue":
                disp_item = "Dark Matter Crystal"
                recipe_dict = ALL_RECIPES[disp_item]
                best = recipe_dict.get("best")
                default = recipe_dict["default"]
                if best and best.get("alternate") and best.get("schematic") and best["schematic"] in unlocked_schematics:
                    recipe = best
                else:
                    recipe = default
                is_slopped = disp_item in sloop_items
                sloop_mult = 2.0 if is_slopped else 1.0
                crystal_rate = overflow_rate * (recipe["outputs"][disp_item] * sloop_mult) / recipe["inputs"][bp]
                trace_specific(disp_item, crystal_rate, recipe, depth=disp_depth)
            elif bp == "Heavy Oil Residue":
                disp_item = "Petroleum Coke"
                recipe = ALL_RECIPES[disp_item]["default"]
                is_slopped = disp_item in sloop_items
                sloop_mult = 2.0 if is_slopped else 1.0
                coke_rate = overflow_rate * (recipe["outputs"][disp_item] * sloop_mult) / recipe["inputs"][bp]
                trace_specific(disp_item, coke_rate, recipe, depth=disp_depth)

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
            "    classDef target fill:#ffb300,stroke:#ffe082,stroke-width:3px,color:#000;",
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
        return full_chart

    phase_flowcharts = {}
    depths = {n.depth for n in nodes_list if n.depth != -1}
    for d in depths:
        core_node_ids = {n.node_id for n in nodes_list if n.depth == d}
        phase_edges = [e for e in edges_list if e.from_node in core_node_ids or e.to_node in core_node_ids]
        connected_node_ids = {e.from_node for e in phase_edges} | {e.to_node for e in phase_edges} | core_node_ids
        phase_nodes = [n for n in nodes_list if n.node_id in connected_node_ids]
        phase_flowcharts[str(d)] = compile_flowchart(phase_nodes, phase_edges, core_depth=d)

    return {"full": full_chart, "phases": phase_flowcharts}
