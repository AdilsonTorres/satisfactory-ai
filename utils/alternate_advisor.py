from typing import Any

# SundownKid's Satisfactory Alternate Recipe Tier List (from guide 3551739887)
SUNDOWNKID_TIER_LIST: dict[str, dict[str, Any]] = {
    # === S-Tier: Must-Have / Game-Changing ===
    "Schematic_Alternate_EnrichedCoal": {
        "name": "Compacted Coal",
        "tier": "S",
        "desc": "Required to get Turbofuel and Rocket Fuel. Not recommended for basic Coal plants.",
    },
    "Schematic_Alternate_DarkMatter_Trap": {
        "name": "Dark Matter Trap",
        "tier": "S",
        "desc": "Effectively halves the SAM needed to make Dark Matter Crystals with no downsides.",
    },
    "Schematic_Alternate_DilutedFuel": {
        "name": "Diluted Fuel",
        "tier": "S",
        "desc": "Drastically boosts fuel output from heavy oil residue using water loops. Vital for power and recycled loops.",
    },
    "Schematic_Alternate_ElectrodeCircuitBoard": {
        "name": "Electrode Circuit Board",
        "tier": "S",
        "desc": "Highly convenient. Can be made solely from waste Heavy Oil Residue and Petroleum Coke, avoiding metals.",
    },
    "Schematic_Alternate_FusedWire": {
        "name": "Fused Wire",
        "tier": "S",
        "desc": "Drastically boosts Wire production by mixing Copper and Caterium. Excellent early on.",
    },
    "Schematic_Alternate_HeavyModularFrame": {
        "name": "Heavy Encased Frame",
        "tier": "S",
        "desc": "Tremendous upgrade. Replaces complex screw lines with Concrete and is highly resource-efficient.",
    },
    "Schematic_Alternate_HeavyOilResidue": {
        "name": "Heavy Oil Residue",
        "tier": "S",
        "desc": "Cornerstone recipe. Maximizes residue to feed downstream Diluted Fuel and Recycled loops.",
    },
    "Schematic_Alternate_IonizedFuel": {
        "name": "Ionized Fuel",
        "tier": "S",
        "desc": "Best Jetpack fuel source. Highly recommended to set up a small facility for Dimensional Depot.",
    },
    "Schematic_Alternate_SteelPipe_Molded": {
        "name": "Molded Steel Pipe",
        "tier": "S",
        "desc": "Highly useful. Replaces standard pipe production with a much less resource-consuming recipe.",
    },
    "Schematic_Alternate_RocketFuel_Nitro": {
        "name": "Nitro Rocket Fuel",
        "tier": "S",
        "desc": "Consumes more Nitrogen but requires far fewer buildings, greatly simplifying infrastructure.",
    },
    "Schematic_Alternate_PureIronIngot": {
        "name": "Pure Iron Ingot",
        "tier": "S",
        "desc": "Uses refinery water loops to increase raw iron node yields significantly.",
    },
    "Schematic_Alternate_PureCopperIngot": {
        "name": "Pure Copper Ingot",
        "tier": "S",
        "desc": "Uses refinery water loops to increase raw copper node yields significantly.",
    },
    "Schematic_Alternate_PureCateriumIngot": {
        "name": "Pure Caterium Ingot",
        "tier": "S",
        "desc": "Uses refinery water loops to increase raw caterium node yields significantly.",
    },
    "Schematic_Alternate_RocketFuel": {
        "name": "Rocket Fuel",
        "tier": "S",
        "desc": "Needed to unlock Nitro Rocket Fuel. Recommended to prioritize.",
        "aliases": ["Research_Sulfur_RocketFuel"],
    },
    "Schematic_Alternate_SloppyAlumina": {
        "name": "Sloppy Alumina",
        "tier": "S",
        "desc": "Pure upgrade. More Alumina Solution with one less output byproduct to manage.",
    },
    "Schematic_Alternate_IngotSteel1": {
        "name": "Solid Steel Ingot",
        "tier": "S",
        "desc": "Best steel recipe. Reduces coal usage and allows utilizing iron ingots to save iron.",
    },
    "Schematic_Alternate_TurboFuel": {
        "name": "Turbofuel",
        "tier": "S",
        "desc": "Needed to unlock Rocket Fuel. Not recommended for power on its own before Rocket Fuel.",
        "aliases": ["Research_Sulfur_TurboFuel"],
    },
    # === A-Tier: Strong / Highly Efficient ===
    "Schematic_Alternate_AluminumBeam": {
        "name": "Aluminum Beam",
        "tier": "A",
        "desc": "Makes formerly resource-heavy steel beams extremely cheap to manufacture.",
    },
    "Schematic_Alternate_AluminumRod": {
        "name": "Aluminum Rod",
        "tier": "A",
        "desc": "Lets you make Rotors purely from aluminum, rendering Steel Rod obsolete.",
    },
    "Schematic_Alternate_BoltedFrame": {
        "name": "Bolted Frame",
        "tier": "A",
        "desc": "Unequivocally the best Modular Frame recipe once combined with Aluminum Beams.",
    },
    "Schematic_Alternate_CoatedIronPlate": {
        "name": "Coated Iron Plate",
        "tier": "A",
        "desc": "Lowers iron needed with minimal plastic investment and high output.",
    },
    "Schematic_Alternate_Computer2": {
        "name": "Crystal Computer",
        "tier": "A",
        "desc": "Uses quartz to consume drastically fewer resources than other computer recipes.",
    },
    "Schematic_Alternate_FlexibleFramework": {
        "name": "Flexible Framework",
        "tier": "A",
        "desc": "Halves the steel beams needed by trading it for Rubber. Pure upgrade.",
    },
    "Schematic_Alternate_HeatExchanger": {
        "name": "Heat Exchanger",
        "tier": "A",
        "desc": "Avoids copper sheets by using rubber, simplifying late game heat sink lines.",
    },
    "Schematic_Alternate_Cable1": {
        "name": "Insulated Cable",
        "tier": "A",
        "desc": "High output. Extremely good when paired with Fused Wire and Recycled Rubber.",
    },
    "Schematic_Alternate_IngotIron": {
        "name": "Iron Alloy Ingot",
        "tier": "A",
        "desc": "Excellent early headstart. Competes well with Pure Iron without requiring water refinery loops.",
    },
    "Schematic_Alternate_OilBasedDiamonds": {
        "name": "Oil-Based Diamonds",
        "tier": "A",
        "desc": "Surprisingly good. Yields massive amounts of diamonds from pure oil nodes for minimal work.",
    },
    "Schematic_Alternate_PinkDiamonds": {
        "name": "Pink Diamonds",
        "tier": "A",
        "desc": "Highly efficient diamond recipe. Uses less coal and very little quartz.",
    },
    "Schematic_Alternate_OCSupercomputer": {
        "name": "OC Supercomputer",
        "tier": "A",
        "desc": "Makes Supercomputers more convenient to produce. Best paired with Crystal Computer.",
    },
    "Schematic_Alternate_AILimiter_Plastic": {
        "name": "Plastic AI Limiter",
        "tier": "A",
        "desc": "Highly useful for nuclear-related lines or if using Insulated Crystal Oscillators.",
    },
    "Schematic_Alternate_PlasticSmartPlating": {
        "name": "Plastic Smart Plating",
        "tier": "A",
        "desc": "Lowers the number of Rotors needed for Smart Plating, trading for plastic.",
    },
    "Schematic_Alternate_PolyesterFabric": {
        "name": "Polyester Fabric",
        "tier": "A",
        "desc": "Mainly used to automate unlimited gas and hazmat filters.",
    },
    "Schematic_Alternate_Cable2": {
        "name": "Quickwire Cable",
        "tier": "A",
        "desc": "Most resource-efficient cable recipe, though output is slightly lower.",
    },
    "Schematic_Alternate_RecycledRubber": {
        "name": "Recycled Rubber",
        "tier": "A",
        "desc": "Excellent. Loop with Recycled Plastic to multiply output using fuel inputs.",
    },
    "Schematic_Alternate_Plastic1": {
        "name": "Recycled Plastic",
        "tier": "A",
        "desc": "Excellent. Loop with Recycled Rubber to multiply output using fuel inputs.",
    },
    "Schematic_Alternate_Motor1": {
        "name": "Rigor Motor",
        "tier": "A",
        "desc": "Undoubtedly the best Motor recipe, replacing standard rotors/stators with Crystal Oscillators.",
    },
    "Schematic_Alternate_Screw2": {
        "name": "Steel Screw",
        "tier": "A",
        "desc": "Excellent late-game recipe. Produces massive screw volumes (260/min) from compact Steel Beams.",
    },
    "Schematic_Alternate_SuperStateComputer": {
        "name": "Super-State Computer",
        "tier": "A",
        "desc": "On par with OC Supercomputer. Recommended to underclock to output exactly 2/minute.",
    },
    "Schematic_Alternate_TurboPressureMotor": {
        "name": "Turbo Pressure Motor",
        "tier": "A",
        "desc": "Best Turbo Motor recipe. Pressure Conversion Cubes are much easier to craft than Radio Control Units.",
    },
    "Schematic_Alternate_WetConcrete": {
        "name": "Wet Concrete",
        "tier": "A",
        "desc": "Highly convenient. Produces massive concrete volume nearby water nodes. The only concrete recipe you need.",
    },
    # === B-Tier: Broadly Good / Small Upgrades ===
    "Schematic_Alternate_CircuitBoard1": {
        "name": "Caterium Circuit Board",
        "tier": "B",
        "desc": "Solid improvement but quickwire-heavy. Electrode Circuit Board is usually preferable.",
    },
    "Schematic_Alternate_Wire2": {
        "name": "Caterium Wire",
        "tier": "B",
        "desc": "Good in places without copper supply, but generally a downgrade from Fused Wire.",
    },
    "Schematic_Alternate_Silica": {
        "name": "Cheap Silica",
        "tier": "B",
        "desc": "Flexible, efficient, and handy late-game for aluminum lines.",
    },
    "Schematic_Alternate_IngotSteel2": {
        "name": "Compacted Steel Ingot",
        "tier": "B",
        "desc": "Saves coal by using compacted coal byproduct from late game fuel chains.",
    },
    "Schematic_Alternate_Silica_Distilled": {
        "name": "Distilled Silica",
        "tier": "B",
        "desc": "High yield Silica recipe but setup is fairly complex.",
    },
    "Schematic_Alternate_Quartz_Purified": {
        "name": "Quartz Purification",
        "tier": "B",
        "desc": "High yield Quartz recipe but setup is fairly complex.",
    },
    "Schematic_Alternate_ElectroAluminumScrap": {
        "name": "Electrode Aluminum Scrap",
        "tier": "B",
        "desc": "Makes Bauxite go further with almost no downside if heavy oil residue is available.",
    },
    "Schematic_Alternate_EncasedIndustrialBeam": {
        "name": "Encased Industrial Pipe",
        "tier": "B",
        "desc": "Excellent early on, but obsoleted by Aluminum Beams later.",
    },
    "Schematic_Alternate_FineConcrete": {
        "name": "Fine Concrete",
        "tier": "B",
        "desc": "Gives massive concrete output early, but Wet Concrete is preferred later.",
    },
    "Schematic_Alternate_UraniumCell1": {
        "name": "Infused Uranium Cell",
        "tier": "B",
        "desc": "Saves uranium processing and makes drone transport safer.",
    },
    "Schematic_Alternate_CrystalOscillator": {
        "name": "Insulated Crystal Oscillator",
        "tier": "B",
        "desc": "Double the throughput of standard oscillators, saving physical space.",
    },
    "Schematic_Alternate_PureQuartzCrystal": {
        "name": "Pure Quartz Crystal",
        "tier": "B",
        "desc": "Very convenient Quartz Crystal recipe that only requires refinery water loops.",
    },
    "Schematic_Alternate_RadioControlSystem": {
        "name": "Radio Control System",
        "tier": "B",
        "desc": "Saves physical space and power by avoiding custom manufacturers.",
    },
    "Schematic_Alternate_CircuitBoard2": {
        "name": "Silicon Circuit Board",
        "tier": "B",
        "desc": "Good when combined with Steamed Copper Sheet, but other alts exceed it.",
    },
    "Schematic_Alternate_SteelCoatedPlate": {
        "name": "Steel Cast Plate",
        "tier": "B",
        "desc": "Decent early game steel plate option, though Coated Iron Plate is better.",
    },
    "Schematic_Alternate_Rotor": {
        "name": "Steel Rotor",
        "tier": "B",
        "desc": "Good for fully phasing out screws if steel rods/screws are not used.",
    },
    "Schematic_Alternate_ModularFrame": {
        "name": "Steeled Frame",
        "tier": "B",
        "desc": "Decent early/mid-game frame recipe but mediocre once aluminum is unlocked.",
    },
    "Schematic_Alternate_ReinforcedIronPlate1": {
        "name": "Stitched Iron Plate",
        "tier": "B",
        "desc": "Makes Phase 1 setup significantly easier by replacing screws with wire.",
    },
    "Schematic_Alternate_NuclearFuelRod1": {
        "name": "Uranium Fuel Unit",
        "tier": "B",
        "desc": "Helps save uranium resources if building mass nuclear layouts.",
    },
    # === F-Tier: Noob Traps / Overrated / Dead Weight ===
    "Schematic_Alternate_AlcladCasing": {
        "name": "Alclad Casing",
        "tier": "F",
        "desc": "Useless. Saves negligible Bauxite while forcing complex Copper Ingot logistics.",
    },
    "Schematic_Alternate_AutomatedSpeedWiring": {
        "name": "Automated Speed Wiring",
        "tier": "F",
        "desc": "Lackluster. Diverting high-speed connectors is not worth the minor stator savings.",
    },
    "Schematic_Alternate_Screw": {
        "name": "Cast Screw",
        "tier": "F",
        "desc": "Noob Trap. Does not improve screw efficiency; makes you skip Iron Rods which is actually a downside. Wait for Steel Screws.",
    },
    "Schematic_Alternate_ClassicBattery": {
        "name": "Classic Battery",
        "tier": "F",
        "desc": "Lackluster. Minor sulfur savings are not worth the large plastic consumption.",
    },
    "Schematic_Alternate_HeavyFlexibleFrame": {
        "name": "Heavy Flexible Frame",
        "tier": "F",
        "desc": "Dead weight. Completely outclassed by Heavy Encased Frame's ridiculously low requirements.",
    },
    "Schematic_Alternate_InstantPlutoniumCell": {
        "name": "Instant Plutonium Cell",
        "tier": "F",
        "desc": "Useless compared to standard plutonium cell production pipelines.",
    },
    "Schematic_Alternate_InstantScrap": {
        "name": "Instant Scrap",
        "tier": "F",
        "desc": "Pointless. Normal aluminum recycling is easily handled via VIP junctions or wastewater sinking.",
    },
    "Schematic_Alternate_PureAluminumIngot": {
        "name": "Pure Aluminum Ingot",
        "tier": "F",
        "desc": "Overrated. Normal ingot recipe is better; consuming silica is a small price for higher aluminum yield.",
    },
    "Schematic_Alternate_RubberConcrete": {
        "name": "Rubber Concrete",
        "tier": "F",
        "desc": "Terrible trade. Wastes valuable rubber to save tiny amounts of limestone.",
    },
    "Schematic_Alternate_TurboHeavyFuel": {
        "name": "Turbo Heavy Fuel",
        "tier": "F",
        "desc": "Obsolete once Diluted Fuel is unlocked. Waste of a hard drive.",
    },
}


def get_recipe_recommendations(unlocked_schematics: list[str]) -> dict[str, Any]:
    """Analyzes unlocked alternate schematics and returns categorized list of unlocked,

    missing, and advice recommendations based on SundownKid's tier list.
    """
    unlocked_set = set(unlocked_schematics)

    results: dict[str, Any] = {
        "unlocked": {"S": [], "A": [], "B": [], "F": []},
        "missing": {"S": [], "A": [], "B": [], "F": []},
        "total_ranked_unlocked": 0,
        "advice": [],
    }

    for schem_id, info in SUNDOWNKID_TIER_LIST.items():
        # Match schematic name (e.g. Schematic_Alternate_Screw)
        # The save parser strips "_C" and splits by "."
        aliases = info.get("aliases", [])
        candidates = [schem_id, *aliases]
        is_unlocked = False
        for cand in candidates:
            cand_suffix = cand.split(".")[-1]
            for u in unlocked_set:
                if u == cand or u.endswith(cand_suffix):
                    is_unlocked = True
                    break
            if is_unlocked:
                break

        tier = info["tier"]
        recipe_data = {
            "id": schem_id,
            "name": info["name"],
            "desc": info["desc"],
        }

        if is_unlocked:
            results["unlocked"][tier].append(recipe_data)
            if tier in ("S", "A", "B"):
                results["total_ranked_unlocked"] += 1
        else:
            results["missing"][tier].append(recipe_data)

    # Formulate recommendations advice
    missing_s = results["missing"]["S"]
    unlocked_f = results["unlocked"]["F"]

    if missing_s:
        results["advice"].append(
            f"Target hard drives to unlock missing S-Tier recipes: {', '.join(r['name'] for r in missing_s)}."
        )

    for f_recipe in unlocked_f:
        if f_recipe["name"] == "Cast Screw":
            # Check if they have Steel Screw unlocked as fallback
            has_steel_screw = any(r["name"] == "Steel Screw" for r in results["unlocked"]["A"])
            if not has_steel_screw:
                results["advice"].append(
                    "You have Cast Screws unlocked (F-Tier/Noob Trap). If you intend to use screws, target Steel Screws (A-Tier) to replace them, or phase out screws entirely."
                )
            else:
                results["advice"].append(
                    "You have Cast Screws unlocked but also have Steel Screws. If using screws, ensure your production is migrated to Steel Screws."
                )

    return results
