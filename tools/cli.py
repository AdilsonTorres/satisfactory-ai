"""
tools/cli.py

Unified CLI entry point for Satisfactory Bot tools.

Usage:
    sbot debug --scan
    sbot debug --find gift_prompt
    sbot debug --screenshot
    sbot capture
    sbot label
    sbot passive --interval 5
    sbot trigger calibration --target hud
    sbot trigger exploration --max-seconds 30
    sbot save
    sbot plan --track
"""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sbot",
        description="Satisfactory Bot — CLI tools",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- debug ---
    debug_parser = subparsers.add_parser("debug", help="Template debugging (no Temporal needed)")
    debug_parser.add_argument("--scan", action="store_true", help="Scan all templates")
    debug_parser.add_argument("--find", metavar="TEMPLATE", help="Look for a template")
    debug_parser.add_argument("--scan-dir", metavar="DIR", help="Run --scan over every PNG in a directory")
    debug_parser.add_argument("--screenshot", action="store_true", help="Screenshot of the current screen")
    debug_parser.add_argument("--config", action="store_true", help="Show current config.toml")
    debug_parser.add_argument("--threshold", type=float, help="Threshold override")

    # --- capture ---
    subparsers.add_parser("capture", help="Interactive template capture tool")

    # --- label ---
    label_parser = subparsers.add_parser("label", help="Review and label captured screenshots")
    label_parser.add_argument("--dir", default="captures", help="Directory with captures [captures]")

    # --- passive ---
    passive_parser = subparsers.add_parser("passive", help="Passive screenshot capture during gameplay")
    passive_parser.add_argument("--interval", type=float, default=4.0, help="Seconds between captures [4.0]")
    passive_parser.add_argument("--max-shots", type=int, default=0, help="Screenshot limit, 0=unlimited [0]")
    passive_parser.add_argument(
        "--dedup-threshold",
        type=float,
        default=0.02,
        help="Deduplication sensitivity, 0=off [0.02]",
    )

    # --- trigger ---
    trigger_parser = subparsers.add_parser("trigger", help="Trigger Temporal workflows")
    trigger_sub = trigger_parser.add_subparsers(dest="workflow", help="Workflow to trigger")

    cal_parser = trigger_sub.add_parser("calibration", help="Visual calibration workflow")
    cal_parser.add_argument("--target", default="hud", choices=["hud", "workshop"], help="Calibration target [hud]")
    cal_parser.add_argument("--resolution", default="2560x1440", help="Game resolution [2560x1440]")

    exp_parser = trigger_sub.add_parser("exploration", help="Exploration workflow")
    exp_parser.add_argument("--id", default="exploration-run", help="Workflow id")
    exp_parser.add_argument("--max-seconds", type=float, default=None, help="Override movement budget")
    exp_parser.add_argument("--ignore-health", action="store_true", help="Skip low-health abort")
    exp_parser.add_argument("--no-return", action="store_true", help="Skip the return-to-base sequence and stay at destination")

    # --- save ---
    save_parser = subparsers.add_parser("save", help="Satisfactory save file diagnostics")
    save_parser.add_argument(
        "filename", nargs="?", help="Path to the Satisfactory save (.sav) file (defaults to latest)"
    )
    save_parser.add_argument("--depot", action="store_true", help="Show Dimensional Depot contents")
    save_parser.add_argument("--collectibles", action="store_true", help="Show collected collectibles summary")
    save_parser.add_argument("--advisor", action="store_true", help="Show alternate recipe advice & recommendations")
    save_parser.add_argument("--track", action="store_true", help="Track save file progress in stats/save_history.json")

    # --- plan ---
    plan_parser = subparsers.add_parser("plan", help="Actionable next-steps report from your current save")
    plan_parser.add_argument(
        "filename", nargs="?", help="Path to the Satisfactory save (.sav) file (defaults to latest)"
    )
    plan_parser.add_argument(
        "--track", action="store_true", help="Record this snapshot in stats/save_history.json after generating the plan"
    )

    # --- plan-production ---
    plan_prod_parser = subparsers.add_parser("plan-production", help="Calculate optimal factory building and raw node requirements for item or coupon rate goals")
    plan_prod_parser.add_argument("--item", help="Target output item name (e.g. 'Modular Frame')")
    plan_prod_parser.add_argument("--rate", type=float, help="Target production rate of the item per minute")
    plan_prod_parser.add_argument("--coupons", type=float, help="Target coupons per minute to produce")
    plan_prod_parser.add_argument("filename", nargs="?", help="Path to the Satisfactory save (.sav) file (defaults to latest)")

    # --- map ---
    subparsers.add_parser("map", help="Build Hover Pack power grid connectivity map and suggested routes")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "debug":
        _run_debug(args)
    elif args.command == "capture":
        _run_capture()
    elif args.command == "label":
        _run_label(args)
    elif args.command == "passive":
        _run_passive(args)
    elif args.command == "trigger":
        _run_trigger(args, trigger_parser)
    elif args.command == "save":
        _run_save_info(args)
    elif args.command == "plan":
        _run_plan(args)
    elif args.command == "plan-production":
        _run_plan_production(args)
    elif args.command == "map":
        _run_map()
    else:
        parser.print_help()


def _run_debug(args: argparse.Namespace) -> None:
    # Lazy import to avoid loading heavy deps when not needed
    from tools.debug_run import cmd_config, cmd_find, cmd_scan, cmd_scan_dir, cmd_screenshot

    if args.scan:
        cmd_scan(args.threshold)
    elif args.find:
        cmd_find(args.find, args.threshold)
    elif args.scan_dir:
        cmd_scan_dir(args.scan_dir, args.threshold)
    elif args.screenshot:
        cmd_screenshot()
    elif args.config:
        cmd_config()
    else:
        print("Use: sbot debug --scan | --find TEMPLATE | --screenshot | --config")


def _run_capture() -> None:
    from tools.capture_template import main as capture_main

    capture_main()


def _run_label(args: argparse.Namespace) -> None:
    from pathlib import Path

    from tools.label_captures import run

    run(Path(args.dir))


def _run_passive(args: argparse.Namespace) -> None:
    from tools.passive_capture import run

    run(args.interval, args.max_shots, args.dedup_threshold)


def _run_trigger(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    import asyncio

    if args.workflow == "calibration":
        asyncio.run(_trigger_calibration(args))
    elif args.workflow == "exploration":
        asyncio.run(_trigger_exploration(args))
    else:
        parser.print_help()


async def _trigger_calibration(args: argparse.Namespace) -> None:
    import json

    from temporalio.client import Client

    from workflows.template_orchestration import TemplateOrchestrationWorkflow

    client = await Client.connect("localhost:7233")
    print(
        f"Connected. Starting TemplateOrchestrationWorkflow(target='{args.target}', resolution='{args.resolution}')..."
    )

    result = await client.execute_workflow(
        TemplateOrchestrationWorkflow.run,
        args=[args.target, args.resolution],
        id="calibration-workflow-run",
        task_queue="satisfactory-bot",
    )
    print("\n=== Workflow completed! Results: ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def _trigger_exploration(args: argparse.Namespace) -> None:
    import json

    from temporalio.client import Client

    from workflows.exploration import ExplorationWorkflow

    client = await Client.connect("localhost:7233")
    print(f"Connected. Starting ExplorationWorkflow(id={args.id}, max_seconds={args.max_seconds}, no_return={args.no_return})...")

    result = await client.execute_workflow(
        ExplorationWorkflow.run,
        args=[args.max_seconds, args.ignore_health, args.no_return],
        id=args.id,
        task_queue="satisfactory-bot",
    )
    print("\n=== Workflow completed ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def _find_latest_save_file() -> str | None:
    import glob
    import os

    paths = [
        os.path.expanduser(
            "~/.local/share/Steam/steamapps/compatdata/526870/pfx/drive_c/users/steamuser/AppData/Local/FactoryGame/Saved/SaveGames/"
        ),
        os.path.expanduser("~/.local/share/FactoryGame/Saved/SaveGames/"),
    ]
    all_files = []
    for p in paths:
        if os.path.exists(p):
            all_files.extend(glob.glob(os.path.join(p, "**", "*.sav"), recursive=True))
    if not all_files:
        return None
    all_files.sort(key=os.path.getmtime, reverse=True)
    return all_files[0]


def _track_save_progress(save) -> None:
    import json
    import os
    from datetime import datetime

    # Get the project root stats folder
    stats_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stats")
    os.makedirs(stats_dir, exist_ok=True)
    history_file = os.path.join(stats_dir, "save_history.json")

    producers_count = sum(save.factory_producers.values())
    extractors_count = sum(save.factory_extractors.values())
    generators_count = sum(save.factory_generators.values())

    coupons_earned = 0
    coupons_avail = 0
    if save.resource_sink:
        coupons_earned = (save.resource_sink.get("coupons_earned_items") or 0) + (
            save.resource_sink.get("coupons_earned_dna") or 0
        )
        coupons_avail = save.resource_sink.get("coupons_available") or 0

    record = {
        "timestamp": datetime.now().isoformat(),
        "filename": os.path.basename(save.filepath),
        "session_name": save.header.get("session_name"),
        "play_duration_seconds": save.header.get("play_duration_seconds", 0),
        "build_version": save.header.get("build_version"),
        "game_phase": save.game_phase,
        "coupons_available": coupons_avail,
        "total_coupons_earned": coupons_earned,
        "unlocked_recipes_count": len(save.recipes),
        "alternate_recipes_unlocked": save.alternate_recipes_unlocked,
        "hard_drives_unlocked": save.hard_drives_unlocked,
        "dimensional_depot_items": len(save.dimensional_depot),
        "producers_count": producers_count,
        "extractors_count": extractors_count,
        "generators_count": generators_count,
        "batteries_count": save.factory_batteries,
    }

    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, encoding="utf-8") as f:
                history = json.load(f)
                if not isinstance(history, list):
                    history = []
        except Exception:
            history = []

    # Check for duplicates
    is_duplicate = False
    for item in history:
        if (
            item.get("session_name") == record["session_name"]
            and item.get("play_duration_seconds") == record["play_duration_seconds"]
        ):
            is_duplicate = True
            break

    if is_duplicate:
        print(
            f"Skipping track: Save state for session '{record['session_name']}' at duration {record['play_duration_seconds']}s already recorded."
        )
    else:
        history.append(record)
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        print("Successfully recorded progress in stats/save_history.json:")
        print(f"  Session:        {record['session_name']}")
        print(f"  Play Duration:  {record['play_duration_seconds'] // 3600} hours")
        print(f"  Coupons Earned: {record['total_coupons_earned']}")
        print(f"  Producers:      {record['producers_count']}")


def _run_save_info(args: argparse.Namespace) -> None:
    import os
    import sys

    from utils.save_parser import SatisfactorySave

    filename = args.filename
    if filename is None:
        filename = _find_latest_save_file()
        if filename is None:
            print("Error: No save file specified and could not auto-discover any Satisfactory save files.")
            sys.exit(1)
        print(f"Auto-discovered latest save file: {filename}")

    if not os.path.exists(filename):
        print(f"Error: File not found: {filename}")
        sys.exit(1)

    print(f"Parsing save file: {filename}...")
    try:
        save = SatisfactorySave(filename)
    except Exception as e:
        print(f"Error parsing save file: {e}")
        sys.exit(1)

    if args.track:
        _track_save_progress(save)

    print("\n=== Save File Info ===")
    print(f"Session Name:           {save.header.get('session_name')}")
    print(f"Play Duration:          {save.header.get('play_duration_seconds', 0) // 3600} hours")
    print(f"Save Date:              {save.header.get('save_datetime')}")
    print(f"Build Version:          {save.header.get('build_version')}")
    print(f"Game Phase:             {save.game_phase}")
    print(f"Active Milestone:       {save.metadata.get('active_schematic', 'None')}")
    print(f"Hard Drives Unlocked:   {save.hard_drives_unlocked}")
    print(f"Recipes Unlocked:       {len(save.recipes)} ({save.alternate_recipes_unlocked} alternates)")
    from utils.alternate_advisor import get_recipe_recommendations

    adv_res = get_recipe_recommendations(save.schematics)
    print(f"SundownKid Ranked Alternates: {adv_res['total_ranked_unlocked']} unlocked (S/A tier)")

    if save.players:
        print("\n=== Players ===")
        for idx, player in enumerate(save.players, 1):
            print(f"Player #{idx}: {player['username']}")
            print(f"  Position: {player['position']}")
            print(f"  Inventory items: {len(player['inventory'])}")

    if save.unlocked_research_trees:
        print("\n=== MAM Research Trees Unlocked ===")
        print("  " + ", ".join(save.unlocked_research_trees))

    if save.resource_sink and save.resource_sink.get("coupons_earned_items") is not None:
        print("\n=== Awesome Sink Progress ===")
        sink = save.resource_sink
        total_earned = sink["coupons_earned_items"] + sink["coupons_earned_dna"]
        print(
            f"  - Total Coupons Earned:  {total_earned} ({sink['coupons_earned_items']} items, {sink['coupons_earned_dna']} DNA)"
        )
        print(f"  - Coupons Available:      {sink['coupons_available']}")
        print(f"  - Total Points Accumulated: {sink['total_points_items']} (items), {sink['total_points_dna']} (DNA)")

    if save.vehicles:
        print("\n=== Vehicle Garage ===")
        for vehicle, count in sorted(save.vehicles.items()):
            print(f"  - {vehicle}: {count}")

    if save.factory_producers or save.factory_extractors or save.factory_generators or save.factory_batteries:
        print("\n=== Factory Floor ===")
        if save.factory_producers:
            print("  Producers:")
            for prod, count in sorted(save.factory_producers.items()):
                print(f"    - {prod}: {count}")
        if save.factory_extractors:
            print("  Extractors:")
            for ext, count in sorted(save.factory_extractors.items()):
                print(f"    - {ext}: {count}")
        if save.factory_generators:
            print("  Power Generators:")
            for gen, count in sorted(save.factory_generators.items()):
                print(f"    - {gen}: {count}")
        if save.factory_batteries:
            print(f"  Power Storages: {save.factory_batteries}")

    if args.depot:
        print("\n=== Dimensional Depot ===")
        if not save.dimensional_depot:
            print("No items stored in Dimensional Depot.")
        else:
            for item in save.dimensional_depot:
                print(f"  - {item['name']}: {item['quantity']}")

    if args.collectibles:
        summary = save.collected_collectibles_summary
        print("\n=== Collected Collectibles ===")
        print(f"  - Somersloops:    {summary['somersloop']}")
        print(f"  - Mercer Spheres: {summary['mercer_sphere']}")
        print(f"  - Blue Slugs:     {summary['power_slug_blue']}")
        print(f"  - Yellow Slugs:   {summary['power_slug_yellow']}")
        print(f"  - Purple Slugs:   {summary['power_slug_purple']}")

    print("\n=== Alternate Recipe Advisor ===")
    s_unlocked = [r["name"] for r in adv_res["unlocked"]["S"]]
    s_missing = [r["name"] for r in adv_res["missing"]["S"]]
    a_unlocked = [r["name"] for r in adv_res["unlocked"]["A"]]
    a_missing = [r["name"] for r in adv_res["missing"]["A"]]
    b_unlocked = [r["name"] for r in adv_res["unlocked"]["B"]]
    b_missing = [r["name"] for r in adv_res["missing"]["B"]]
    f_unlocked = [r["name"] for r in adv_res["unlocked"]["F"]]

    print(f"  - S-Tier Unlocked: {', '.join(s_unlocked) or 'None'}")
    print(f"  - S-Tier Missing:  {', '.join(s_missing) or 'None'}")
    print(f"  - A-Tier Unlocked: {', '.join(a_unlocked) or 'None'}")
    print(f"  - A-Tier Missing:  {', '.join(a_missing) or 'None'}")
    print(f"  - B-Tier Unlocked: {', '.join(b_unlocked) or 'None'}")
    print(f"  - B-Tier Missing:  {', '.join(b_missing) or 'None'}")
    if f_unlocked:
        print(f"  - Warning F-Tier Unlocked: {', '.join(f_unlocked)} (Noob trap!)")

    if adv_res["advice"]:
        print("\n=== Advisor Recommendations ===")
        for advice in adv_res["advice"]:
            print(f"  * {advice}")

    if args.advisor:
        print("\n=== Alternate Recipe Tier Descriptions ===")
        if adv_res["missing"]["S"]:
            print("  S-Tier Missing Details:")
            for r in adv_res["missing"]["S"]:
                print(f"    * {r['name']}: {r['desc']}")
        if adv_res["missing"]["A"]:
            print("  A-Tier Missing Details:")
            for r in adv_res["missing"]["A"]:
                print(f"    * {r['name']}: {r['desc']}")
        if adv_res["missing"]["B"]:
            print("  B-Tier Missing Details:")
            for r in adv_res["missing"]["B"]:
                print(f"    * {r['name']}: {r['desc']}")


def _run_plan(args: argparse.Namespace) -> None:
    import os
    import sys

    from utils.gameplay_plan import build_gameplay_plan, load_save_history
    from utils.save_parser import SatisfactorySave

    filename = args.filename
    if filename is None:
        filename = _find_latest_save_file()
        if filename is None:
            print("Error: No save file specified and could not auto-discover any Satisfactory save files.")
            sys.exit(1)
        print(f"Auto-discovered latest save file: {filename}")

    if not os.path.exists(filename):
        print(f"Error: File not found: {filename}")
        sys.exit(1)

    print(f"Parsing save file: {filename}...")
    try:
        save = SatisfactorySave(filename)
    except Exception as e:
        print(f"Error parsing save file: {e}")
        sys.exit(1)

    stats_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stats")
    history = load_save_history(os.path.join(stats_dir, "save_history.json"))
    plan = build_gameplay_plan(save, history)

    print("\n=== Gameplay Plan ===")
    m = plan["milestone"]
    print(f"Session: {save.header.get('session_name')}  |  Phase: {m['game_phase']}")
    print(f"Active Milestone: {m['active_schematic'] or 'None'}")
    print(
        f"Purchased Schematics: {m['purchased_schematics_count']}  |  Hard Drives Unlocked: {m['hard_drives_unlocked']}"
    )

    print("\n--- Next Alternate Recipes To Target ---")
    r = plan["recipes"]
    missing_s = [x["name"] for x in r["missing"]["S"]]
    missing_a = [x["name"] for x in r["missing"]["A"]]
    if missing_s:
        print(f"  S-Tier missing: {', '.join(missing_s)}")
    if missing_a:
        print(f"  A-Tier missing: {', '.join(missing_a)}")
    for advice in r["advice"]:
        print(f"  * {advice}")
    if not missing_s and not missing_a and not r["advice"]:
        print("  You have every S/A-Tier alternate recipe unlocked.")

    print("\n--- Resource Sink & Depot ---")
    res = plan["resources"]
    if res["coupons_available"]:
        print(f"  Coupons Available: {res['coupons_available']} (spend them!)")
    else:
        print("  No coupons currently available.")
    print(f"  Total Coupons Earned: {res['total_coupons_earned']}")
    print(f"  Dimensional Depot item types stored: {res['dimensional_depot_item_types']}")

    print("\n--- Factory Snapshot ---")
    f = plan["factory"]
    print(
        f"  Producers: {f['producers']}  Extractors: {f['extractors']}  Generators: {f['generators']}  Batteries: {f['batteries']}"
    )

    if plan["delta"]:
        d = plan["delta"]
        print(f"\n--- Since Last Snapshot ({d['prior_timestamp']}) ---")
        print(
            f"  +{d['hours_played_delta']}h played, +{d['recipes_delta']} recipes, "
            f"+{d['alternates_delta']} alternates, +{d['coupons_earned_delta']} coupons, "
            f"+{d['producers_delta']} producers"
        )
    else:
        print("\n--- Since Last Snapshot ---")
        print(
            "  No prior snapshot found. Run `sbot plan --track` (or `sbot save --track`) periodically to see progress deltas here."
        )

    print(f"\n--- Guide Tips ({plan['guide_doc_path']}) ---")
    if plan["guide_sections"]:
        for h in plan["guide_sections"]:
            print(f"  * {h}")
    else:
        print("  (guide doc not found)")

    if args.track:
        _track_save_progress(save)


def _run_map() -> None:
    from tools.map_power import generate_power_map

    result = generate_power_map()
    if not result:
        return

    map_data = result["map"]
    pois = result["pois"]
    stats = map_data["stats"]

    print("\n================== Hover Pack Power Grid Map ==================")
    print(f"Total Active Power Nodes:    {stats['total_active_nodes']}")
    print(f"Total Power Wires Matched:   {stats['total_wires']}")
    print(f"Reachable Nodes from Player: {stats['reachable_nodes_count']}")
    print(f"Reachable Network Length:    {stats['reachable_network_length_meters']:.1f} meters ({stats['reachable_network_length_meters']/1000.0:.2f} km)")
    print(f"Is Player Powered Right Now: {'YES' if stats['is_currently_powered'] else 'NO'}")

    print("\n================== Discovered Points of Interest ==================")
    print(f"Lizard Doggos found:         {len(pois['lizard_doggos'])}")
    print(f"Drop Pods (Crash Sites):     {len(pois['drop_pods'])}")
    print(f"Fauna Nests (Crab Hatchers): {len(pois['enemy_nests'])}")
    print(f"Enemy Threat Spots (Remains): {len(pois['enemy_remains'])}")
    print(f"Resource Nodes & Geysers:    {len(pois['resource_nodes']) + len(pois['geysers'])}")

    routes = map_data.get("suggested_routes", [])
    if routes:
        print("\nSuggested Flying Routes (Hover Pack Only):")
        for r in routes:
            print(f"\n  * Route: {r['name']}")
            print(f"    Total Legs: {r['total_legs']}, Total Distance: {r['total_distance_meters']:.1f} meters")
            print("    Legs Configuration (copy to config.toml):")
            for _i, leg in enumerate(r["legs"]):
                keys_str = ", ".join(f'"{k}"' for k in leg["keys"])
                print("      [[exploration.route]]")
                print(f"      keys = [{keys_str}]")
                print(f"      duration = {leg['duration']}")
                print(f"      turn_dx = 0  # direction_yaw={leg['direction_yaw']}°")
    else:
        if not stats["is_currently_powered"]:
            print("\n[Tip] Walk closer to your power poles (within 30m) to get powered, then run this command again to trace your reachable paths!")


def _run_plan_production(args: argparse.Namespace) -> None:
    import os
    import sys
    from tools.factory_planner import generate_production_plan

    filename = args.filename
    if filename is None:
        filename = _find_latest_save_file()
        if filename is None:
            print("Error: No save file specified and could not auto-discover any Satisfactory save files.")
            sys.exit(1)
        print(f"Auto-discovered latest save file: {filename}")

    if not os.path.exists(filename):
        print(f"Error: File not found: {filename}")
        sys.exit(1)

    try:
        plan = generate_production_plan(
            target_item=args.item,
            target_rate=args.rate,
            coupons_per_minute=args.coupons,
            save_file_path=filename
        )
    except Exception as e:
        print(f"Error generating production plan: {e}")
        sys.exit(1)

    # Print output report
    print("\n" + "="*55)
    print("=== FACTORY PRODUCTION PLAN ===")
    print("="*55)
    
    if plan["coupons_per_minute"] is not None:
        print(f"Goal:           {plan['coupons_per_minute']:.2f} Coupons/minute")
        print(f"Current count:  {plan['current_coupons']} coupons earned")
        print(f"Required rate:  {plan['points_required']:.2f} Awesome Sink Points/min")
        print(f"Plan Target:    {plan['target_rate']:.4f} {plan['target_item']}/min")
    else:
        print(f"Goal Target:    {plan['target_rate']:.2f} {plan['target_item']}/min")

    if plan["warnings"]:
        print("\n[WARNINGS]")
        for w in plan["warnings"]:
            print(f"  * {w}")
            
    print("\n--- Raw Resource Node Extraction Requirements ---")
    print(f"{'Raw Item':<25} | {'Required Rate':<15} | {'Mk.3 Miners (250%)':<20} | {'Details'}")
    print("-" * 85)
    for raw_item, details in sorted(plan["raw_materials"].items()):
        miner_info = plan["miners"].get(raw_item, {"extractors_needed": 0.0, "details": ""})
        print(f"{raw_item:<25} | {details:<15.2f} | {miner_info['extractors_needed']:<20.2f} | {miner_info['details']}")

    print("\n--- Production Steps & Buildings Required ---")
    print(f"{'Output Item':<28} | {'Recipe Used':<28} | {'Machine Type':<15} | {'Machines':<10} | {'Status'}")
    print("-" * 95)
    for step in sorted(plan["steps"], key=lambda x: x["item"]):
        status = "Unlocked"
        if step["alternate"]:
            status = "Unlocked (Alt)" if step["unlocked"] else "[LOCKED]"
        print(f"{step['item']:<28} | {step['recipe_name']:<28} | {step['machine']:<15} | {step['machine_count']:<10.2f} | {status}")
        
    print("="*55)


if __name__ == "__main__":
    main()
