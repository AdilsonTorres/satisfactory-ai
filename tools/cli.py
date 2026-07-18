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


def create_parser() -> argparse.ArgumentParser:
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
    exp_parser.add_argument(
        "--no-return", action="store_true", help="Skip the return-to-base sequence and stay at destination"
    )

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
    plan_prod_parser = subparsers.add_parser(
        "plan-production",
        help="Calculate optimal factory building and raw node requirements for item or coupon rate goals",
    )
    plan_prod_parser.add_argument("--item", help="Target output item name (e.g. 'Modular Frame')")
    plan_prod_parser.add_argument("--rate", type=float, help="Target production rate of the item per minute")
    plan_prod_parser.add_argument("--coupons", type=float, help="Target coupons per minute to produce")
    plan_prod_parser.add_argument("--draw", action="store_true", help="Draw Mermaid flowchart of the factory layout")
    plan_prod_parser.add_argument("--draw-html", action="store_true", help="Draw flowchart and open in browser")
    plan_prod_parser.add_argument(
        "filename", nargs="?", help="Path to the Satisfactory save (.sav) file (defaults to latest)"
    )

    # --- plan-late-game ---
    plan_lg_parser = subparsers.add_parser(
        "plan-late-game",
        help="Calculate late-game specialized factory scaling, power shards, somersloops, and fuel generators",
        description=(
            "Calculate late-game specialized factory scaling, power shards, somersloops, and fuel generators.\n\n"
            "Examples:\n"
            '  sbot plan-late-game --item "Ballistic Warp Drive" --rate 10\n'
            '  sbot plan-late-game --sloops "Superposition Oscillator" "Dark Matter Crystal"\n'
            "  sbot plan-late-game --recipe-multiplier 0.75"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    plan_lg_parser.add_argument(
        "--item", default="Ballistic Warp Drive", help="Target output item name (default: 'Ballistic Warp Drive')"
    )
    plan_lg_parser.add_argument(
        "--rate", type=float, default=5.0, help="Target production rate of the item per minute (default: 5.0)"
    )
    plan_lg_parser.add_argument("--no-overclock", action="store_true", help="Disable default 250% shard overclocking")
    plan_lg_parser.add_argument(
        "--sloops",
        nargs="*",
        default=[],
        help=(
            "List of items to amplify using Somersloops (doubles output rate). "
            "Pass as space-separated names (use quotes for names with spaces), "
            'e.g., --sloops "Superposition Oscillator" "Dark Matter Crystal"'
        ),
    )
    plan_lg_parser.add_argument(
        "--recipe-multiplier", type=float, default=1.0, help="Recipe cost multiplier (e.g. 0.75)"
    )
    plan_lg_parser.add_argument("--draw", action="store_true", help="Draw Mermaid flowchart of the factory layout")
    plan_lg_parser.add_argument("--draw-html", action="store_true", help="Draw flowchart and open in browser")
    plan_lg_parser.add_argument(
        "filename", nargs="?", help="Path to the Satisfactory save (.sav) file (defaults to latest)"
    )

    # --- map ---
    map_parser = subparsers.add_parser("map", help="Build Hover Pack power grid connectivity map and suggested routes")
    map_parser.add_argument("--draw-html", action="store_true", help="Draw map and open in browser")

    # --- status ---
    subparsers.add_parser("status", help="Show active Temporal workflow status and telemetry")

    # --- dashboard ---
    dash_parser = subparsers.add_parser(
        "dashboard", help="Start local web dashboard monitoring loop status and screenshot Crops"
    )
    dash_parser.add_argument("--port", type=int, default=8080, help="Local server port [8080]")

    # --- start ---
    start_parser = subparsers.add_parser(
        "start", help="Boot the entire stack (Docker Compose, Host Worker, and Dashboard)"
    )
    start_parser.add_argument("--port", type=int, default=8080, help="Local server port [8080]")

    # --- schedules ---
    sched_parser = subparsers.add_parser("schedules", help="Manage Temporal gift-farming schedules")
    sched_sub = sched_parser.add_subparsers(dest="action", required=True)
    sched_sub.add_parser("list", help="List all active gift-farming schedules")

    st_p = sched_sub.add_parser("status", help="Show status of schedules")
    st_p.add_argument("--name", default=None, help="Schedule name")

    p_p = sched_sub.add_parser("pause", help="Pause a schedule")
    p_p.add_argument("--name", default=None, help="Schedule name")

    up_p = sched_sub.add_parser("unpause", help="Unpause a schedule")
    up_p.add_argument("--name", default=None, help="Schedule name")

    d_p = sched_sub.add_parser("delete", help="Delete a schedule")
    d_p.add_argument("--name", default=None, help="Schedule name")

    c_p = sched_sub.add_parser("create", help="Create/replace a named start+stop window")
    c_p.add_argument("--name", default="daily", help="Window name [daily]")
    c_p.add_argument("--start", default="08:00", help="Window start HH:MM")
    c_p.add_argument("--stop", default="23:00", help="Window stop HH:MM")
    c_p.add_argument("--no-stop", action="store_true", help="Run 24/7 with no stop schedule (always-on mode)")
    c_p.add_argument("--timezone", default=None, help="IANA timezone name")
    c_p.add_argument("--ammo-per-craft", type=int, default=50)
    c_p.add_argument("--screenshot-every-cycles", type=int, default=10)
    c_p.add_argument("--interval", type=float, default=50.0)

    return parser


def main() -> None:
    parser = create_parser()
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
        _run_trigger(args, parser)
    elif args.command == "save":
        _run_save_info(args)
    elif args.command == "plan":
        _run_plan(args)
    elif args.command == "plan-production":
        _run_plan_production(args)
    elif args.command == "plan-late-game":
        _run_plan_late_game(args)
    elif args.command == "map":
        _run_map(args)
    elif args.command == "status":
        import asyncio

        asyncio.run(_run_status())
    elif args.command == "dashboard":
        _run_dashboard(args)
    elif args.command == "start":
        _run_start(args)
    elif args.command == "schedules":
        import asyncio

        asyncio.run(_run_schedules(args))
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
    print(
        f"Connected. Starting ExplorationWorkflow(id={args.id}, max_seconds={args.max_seconds}, no_return={args.no_return})..."
    )

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

    adv_res = get_recipe_recommendations(save.schematics + save.recipes)
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
    c_unlocked = [r["name"] for r in adv_res["unlocked"]["C"]]
    c_missing = [r["name"] for r in adv_res["missing"]["C"]]
    d_unlocked = [r["name"] for r in adv_res["unlocked"]["D"]]
    d_missing = [r["name"] for r in adv_res["missing"]["D"]]
    f_unlocked = [r["name"] for r in adv_res["unlocked"]["F"]]

    print(f"  - S-Tier Unlocked: {', '.join(s_unlocked) or 'None'}")
    print(f"  - S-Tier Missing:  {', '.join(s_missing) or 'None'}")
    print(f"  - A-Tier Unlocked: {', '.join(a_unlocked) or 'None'}")
    print(f"  - A-Tier Missing:  {', '.join(a_missing) or 'None'}")
    print(f"  - B-Tier Unlocked: {', '.join(b_unlocked) or 'None'}")
    print(f"  - B-Tier Missing:  {', '.join(b_missing) or 'None'}")
    print(f"  - C-Tier Unlocked: {', '.join(c_unlocked) or 'None'}")
    print(f"  - C-Tier Missing:  {', '.join(c_missing) or 'None'}")
    print(f"  - D-Tier Unlocked: {', '.join(d_unlocked) or 'None'}")
    print(f"  - D-Tier Missing:  {', '.join(d_missing) or 'None'}")
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
        if adv_res["missing"]["C"]:
            print("  C-Tier Missing Details:")
            for r in adv_res["missing"]["C"]:
                print(f"    * {r['name']}: {r['desc']}")
        if adv_res["missing"]["D"]:
            print("  D-Tier Missing Details:")
            for r in adv_res["missing"]["D"]:
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


def _save_map_html(map_data: dict, pois: dict) -> str:
    import contextlib
    import os
    import webbrowser
    from pathlib import Path

    stats_dir = Path("stats")
    stats_dir.mkdir(exist_ok=True)
    html_file = stats_dir / "reachable_power_map.html"

    # 1. Collect all coordinates to compute bounding box
    all_x = []
    all_y = []

    player_pos = map_data["stats"]["player_position"]
    all_x.append(player_pos[0])
    all_y.append(player_pos[1])

    nodes_dict = {n["id"]: n for n in map_data["reachable_nodes"]}
    for node in map_data["reachable_nodes"]:
        all_x.append(node["pos"][0])
        all_y.append(node["pos"][1])

    for p_list in pois.values():
        for p in p_list:
            if "pos" in p:
                all_x.append(p["pos"][0])
                all_y.append(p["pos"][1])
            elif "position" in p:
                all_x.append(p["position"][0])
                all_y.append(p["position"][1])

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    span_x = max_x - min_x
    span_y = max_y - min_y
    if span_x < 20000:
        min_x -= (20000 - span_x) / 2
        max_x += (20000 - span_x) / 2
    if span_y < 20000:
        min_y -= (20000 - span_y) / 2
        max_y += (20000 - span_y) / 2

    padding = 5000.0
    min_x -= padding
    max_x += padding
    min_y -= padding
    max_y += padding

    width = max_x - min_x
    height = max_y - min_y

    def map_x(v):
        return (v - min_x) / width * 1000

    def map_y(v):
        return 1000 - ((v - min_y) / height * 1000)

    # 2. Render SVG elements
    svg_elements = []

    # Hover Pack coverage circles (underneath wires)
    for node in map_data["reachable_nodes"]:
        r_px = (node["range"] / width) * 1000
        cx = map_x(node["pos"][0])
        cy = map_y(node["pos"][1])
        svg_elements.append(f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r_px:.1f}" class="node-range" />')

    # Reachable Wires
    for w in map_data["reachable_wires"]:
        node_a = nodes_dict.get(w["node_a"])
        node_b = nodes_dict.get(w["node_b"])
        if node_a and node_b:
            ax, ay = map_x(node_a["pos"][0]), map_y(node_a["pos"][1])
            bx, by = map_x(node_b["pos"][0]), map_y(node_b["pos"][1])
            svg_elements.append(f'  <line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" class="wire" />')

    # Power Nodes
    for node in map_data["reachable_nodes"]:
        cx = map_x(node["pos"][0])
        cy = map_y(node["pos"][1])
        label = node["type"].split(".")[-1].removesuffix("_C")
        svg_elements.append(
            f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" class="power-node" data-tooltip="Power Node: {label}" />'
        )

    # POIs (Doggos, Crash Sites, Nests)
    for _idx, doggo in enumerate(pois.get("lizard_doggos", [])):
        pos = doggo.get("pos") or doggo.get("position")
        if pos:
            cx, cy = map_x(pos[0]), map_y(pos[1])
            svg_elements.append(
                f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" class="poi-doggo" data-tooltip="Lizard Doggo: {doggo.get("name", "Wild")}" />'
            )

    for _idx, pod in enumerate(pois.get("drop_pods", [])):
        pos = pod.get("pos") or pod.get("position")
        if pos:
            cx, cy = map_x(pos[0]), map_y(pos[1])
            svg_elements.append(
                f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" class="poi-pod" data-tooltip="Crash Site (Drop Pod)" />'
            )

    for _idx, nest in enumerate(pois.get("enemy_nests", [])):
        pos = nest.get("pos") or nest.get("position")
        if pos:
            cx, cy = map_x(pos[0]), map_y(pos[1])
            svg_elements.append(
                f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" class="poi-nest" data-tooltip="Fauna Nest (Hazard)" />'
            )

    for _idx, res in enumerate(pois.get("resource_nodes", [])):
        pos = res.get("pos") or res.get("position")
        if pos:
            cx, cy = map_x(pos[0]), map_y(pos[1])
            purity = res.get("purity", "RP_Normal").replace("RP_", "")
            extracted = "Extracted" if res.get("extracted") else "Unextracted"
            res_type = res.get("type", "Unknown")
            svg_elements.append(
                f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" class="poi-resource res-{res_type.lower()}" data-extracted="{str(res.get("extracted")).lower()}" data-tooltip="{res_type} Node ({purity}) - {extracted}" />'
            )

    for _idx, g in enumerate(pois.get("geysers", [])):
        pos = g.get("pos") or g.get("position")
        if pos:
            cx, cy = map_x(pos[0]), map_y(pos[1])
            extracted = "Extracted" if g.get("extracted") else "Unextracted"
            svg_elements.append(
                f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" class="poi-geyser" data-extracted="{str(g.get("extracted")).lower()}" data-tooltip="Geyser - {extracted}" />'
            )

    # Player position
    px = map_x(player_pos[0])
    py = map_y(player_pos[1])
    svg_elements.append(f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="12" class="player-pulse" />')
    svg_elements.append(
        f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="5" class="player-dot" data-tooltip="Player Position" />'
    )

    svg_content = "\n".join(svg_elements)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Hover Pack Power Grid Map</title>
  <style>
    body {{
      background-color: #121212;
      color: #ffffff;
      font-family: 'Inter', sans-serif;
      margin: 0;
      padding: 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    h1 {{
      color: #ff9800;
      margin-bottom: 5px;
    }}
    p {{
      color: #90a4ae;
      margin-top: 0;
      margin-bottom: 20px;
    }}
    .map-container {{
      position: relative;
      background-color: #1e1e1e;
      border-radius: 12px;
      padding: 10px;
      box-shadow: 0 8px 16px rgba(0,0,0,0.5);
      width: 100%;
      max-width: 900px;
    }}
    svg {{
      width: 100%;
      height: auto;
      border: 1px solid #37474f;
      border-radius: 8px;
      background-color: #0d0d0d;
    }}
    .wire {{
      stroke: #00e5ff;
      stroke-width: 2px;
      stroke-linecap: round;
      opacity: 0.8;
    }}
    .power-node {{
      fill: #ffea00;
      stroke: #121212;
      stroke-width: 1px;
      cursor: pointer;
    }}
    .node-range {{
      fill: #00e5ff;
      fill-opacity: 0.03;
      stroke: #00e5ff;
      stroke-width: 1px;
      stroke-opacity: 0.2;
      stroke-dasharray: 4;
    }}
    .poi-doggo {{
      fill: #ffab00;
      stroke: #121212;
      stroke-width: 1px;
      cursor: pointer;
    }}
    .poi-pod {{
      fill: #00e676;
      stroke: #121212;
      stroke-width: 1px;
      cursor: pointer;
    }}
    .poi-nest {{
      fill: #ff1744;
      stroke: #121212;
      stroke-width: 1px;
      cursor: pointer;
    }}
    .poi-resource {{
      display: none;
      stroke: #121212;
      stroke-width: 1px;
      cursor: pointer;
      opacity: 0.85;
    }}
    .poi-geyser {{
      display: none;
      stroke: #121212;
      stroke-width: 1px;
      cursor: pointer;
      opacity: 0.85;
    }}
    circle[data-extracted="true"] {{
      stroke: #00e676 !important;
      stroke-width: 2.5px !important;
    }}
    .res-iron {{ fill: #cfd8dc; }}
    .res-copper {{ fill: #ff7043; }}
    .res-coal {{ fill: #37474f; }}
    .res-limestone {{ fill: #eceff1; }}
    .res-caterium {{ fill: #ffd54f; }}
    .res-bauxite {{ fill: #ef5350; }}
    .res-quartz {{ fill: #80deea; }}
    .res-sulfur {{ fill: #fff59d; }}
    .res-uranium {{ fill: #a5d6a7; }}
    .res-unknown {{ fill: #757575; }}
    .player-dot {{
      fill: #00e676;
      stroke: #ffffff;
      stroke-width: 2px;
      cursor: pointer;
    }}
    .player-pulse {{
      fill: none;
      stroke: #00e676;
      stroke-width: 2px;
      transform-origin: center;
      animation: pulse-ring 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
    }}
    @keyframes pulse-ring {{
      0% {{ transform: scale(0.3); opacity: 0.8; }}
      80%, 100% {{ transform: scale(1.8); opacity: 0; }}
    }}
    .tooltip {{
      position: absolute;
      background: rgba(0,0,0,0.85);
      border: 1px solid #ff9800;
      border-radius: 4px;
      padding: 6px 10px;
      color: #fff;
      font-size: 12px;
      pointer-events: none;
      display: none;
      z-index: 100;
    }}
    .legend {{
      margin-top: 20px;
      display: flex;
      gap: 20px;
      flex-wrap: wrap;
      justify-content: center;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
    }}
    .legend-color {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
    }}
  </style>
</head>
<body>
  <h1>Hover Pack Grid Map</h1>
  <p>Live cartography of reachable power coverage and points of interest</p>
  <div class="map-container">
    <svg viewBox="0 0 1000 1000" id="map-svg">
{svg_content}
    </svg>
    <div class="tooltip" id="map-tooltip"></div>
  </div>

  <div style="margin-top: 15px; text-align: center;">
    <button id="toggle-resources" style="background-color: #ff9800; border: none; padding: 8px 16px; border-radius: 4px; color: #000; font-weight: bold; cursor: pointer; font-family: sans-serif;">Toggle Resource Nodes Overlay</button>
  </div>

  <div class="legend">
    <div class="legend-item"><div class="legend-color" style="background: #00e676;"></div>Player</div>
    <div class="legend-item"><div class="legend-color" style="background: #ffea00;"></div>Power Pole / Tower</div>
    <div class="legend-item"><div class="legend-color" style="background: #00e5ff; border: 1px dashed rgba(0,229,255,0.5);"></div>Hover Pack Range</div>
    <div class="legend-item"><div class="legend-color" style="background: #ffab00;"></div>Lizard Doggo</div>
    <div class="legend-item"><div class="legend-color" style="background: #ff1744;"></div>Fauna Nest (Hazard)</div>
    <div class="legend-item"><div class="legend-color" style="background: #00e676; border: 1px solid #121212;"></div>Crash Site (Drop Pod)</div>
    <div class="legend-item"><div class="legend-color" style="background: #ef5350; border: 2px solid #00e676;"></div>Extracted Node (Green Outline)</div>
  </div>

  <script>
    const svg = document.getElementById('map-svg');
    const tooltip = document.getElementById('map-tooltip');

    let showResources = false;
    document.getElementById('toggle-resources').addEventListener('click', () => {{
      showResources = !showResources;
      const displayStyle = showResources ? 'block' : 'none';
      document.querySelectorAll('.poi-resource').forEach(el => el.style.display = displayStyle);
      document.querySelectorAll('.poi-geyser').forEach(el => el.style.display = displayStyle);
      const btn = document.getElementById('toggle-resources');
      btn.style.backgroundColor = showResources ? '#00e676' : '#ff9800';
    }});

    svg.addEventListener('mouseover', (e) => {{
      const text = e.target.getAttribute('data-tooltip');
      if (text) {{
        tooltip.textContent = text;
        tooltip.style.display = 'block';
      }}
    }});

    svg.addEventListener('mousemove', (e) => {{
      const rect = svg.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      tooltip.style.left = (x + 15) + 'px';
      tooltip.style.top = (y + 15) + 'px';
    }});

    svg.addEventListener('mouseout', (e) => {{
      if (e.target.getAttribute('data-tooltip')) {{
        tooltip.style.display = 'none';
      }}
    }});
  </script>
</body>
</html>
"""
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    abs_path = os.path.abspath(html_file)
    with contextlib.suppress(Exception):
        webbrowser.open(f"file://{abs_path}")
    return str(html_file)


def _run_map(args: argparse.Namespace) -> None:
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
    print(
        f"Reachable Network Length:    {stats['reachable_network_length_meters']:.1f} meters ({stats['reachable_network_length_meters'] / 1000.0:.2f} km)"
    )
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
            print(
                "\n[Tip] Walk closer to your power poles (within 30m) to get powered, then run this command again to trace your reachable paths!"
            )

    if args.draw_html:
        path = _save_map_html(map_data, pois)
        print(f"\nInteractive Map exported to: {path}")


def _run_dashboard(args: argparse.Namespace) -> None:
    from tools.dashboard import start_server

    start_server(args.port)


def _run_start(args: argparse.Namespace) -> None:
    import subprocess
    import sys

    from tools.dashboard import start_server

    print("\n==================================================")
    print("  Booting Satisfactory Bot Unified Stack...")
    print("==================================================")

    # 1. Start Docker compose
    print("\n[1/3] Launching Docker stack (Temporal, PostgreSQL)...")
    try:
        subprocess.run(["docker", "compose", "up", "-d"], check=True)
        print("Docker stack launched successfully.")
    except Exception as exc:
        print(f"Error starting docker-compose: {exc}", file=sys.stderr)
        print("Make sure Docker daemon is running.", file=sys.stderr)
        sys.exit(1)

    # 2. Launch Host Worker
    print("\n[2/3] Spawning Host GUI Worker process...")
    worker_proc = None
    try:
        worker_proc = subprocess.Popen([sys.executable, "workers/worker.py"])
        print(f"Host GUI Worker process spawned (PID: {worker_proc.pid}).")
    except Exception as exc:
        print(f"Error starting host worker: {exc}", file=sys.stderr)
        sys.exit(1)

    # 3. Start Dashboard Server
    print("\n[3/3] Starting Gameplay Dashboard Server...")
    try:
        start_server(args.port)
    finally:
        if worker_proc and worker_proc.poll() is None:
            print("\nShutting down Host GUI Worker process...")
            worker_proc.terminate()
            try:
                worker_proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                worker_proc.kill()
            print("Host GUI Worker shutdown finished.")


def _get_acronym_mapping(valid_items: set[str]) -> dict[str, str]:
    """Generate a mapping from uppercase acronyms of multi-word items to full names."""
    mapping: dict[str, str | None] = {}
    for item in valid_items:
        words = [w for w in item.split() if w]
        if len(words) >= 2:
            acronym = "".join(w[0].upper() for w in words if w[0].isalnum())
            if acronym:
                if acronym in mapping:
                    mapping[acronym] = None
                else:
                    mapping[acronym] = item
    return {k: v for k, v in mapping.items() if v is not None}


def _resolve_item_interactive(item: str, valid_items: set[str], label: str = "Item") -> str:
    """Resolve an item name interactively, offering fuzzy suggestions on mismatch.

    Returns the validated (possibly corrected) item name, or calls sys.exit(1)
    if the user declines all suggestions.
    """
    import difflib

    if item in valid_items:
        return item

    # Check for exact uppercase shortname/acronym match
    acronyms = _get_acronym_mapping(valid_items)
    if item in acronyms:
        resolved = acronyms[item]
        print(f"  \u2192 Resolved shortcut '{item}' to '{resolved}'")
        return resolved

    suggestions = difflib.get_close_matches(item, sorted(valid_items), n=5, cutoff=0.45)

    if not suggestions:
        print(f"Error: {label} '{item}' is not recognised and no similar items were found.")
        sys.exit(1)

    if len(suggestions) == 1:
        answer = input(f"{label} '{item}' not found. Did you mean '{suggestions[0]}'? [Y/n]: ").strip().lower()
        if answer in ("", "y", "yes"):
            print(f"  \u2192 Using '{suggestions[0]}'")
            return suggestions[0]
        print("Aborted.")
        sys.exit(1)

    # Multiple suggestions — numbered list
    print(f"{label} '{item}' not found. Did you mean one of these?")
    for i, s in enumerate(suggestions, 1):
        print(f"  {i}. {s}")
    print("  0. None of these (abort)")

    choice = input("Enter number: ").strip()
    try:
        idx = int(choice)
    except ValueError:
        print("Invalid choice. Aborted.")
        sys.exit(1)

    if idx == 0:
        print("Aborted.")
        sys.exit(1)
    if 1 <= idx <= len(suggestions):
        selected = suggestions[idx - 1]
        print(f"  \u2192 Using '{selected}'")
        return selected

    print("Invalid choice. Aborted.")
    sys.exit(1)


def _save_flowchart_html(markup: str, target_name: str) -> str:
    import os
    import webbrowser
    from pathlib import Path

    stats_dir = Path("stats")
    stats_dir.mkdir(exist_ok=True)

    clean_target = target_name.lower().replace(" ", "_")
    html_file = stats_dir / f"factory_plan_{clean_target}.html"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Satisfactory Factory Planner - {target_name}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <script>
    mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
  </script>
  <style>
    body {{
      background-color: #121212;
      color: #ffffff;
      font-family: 'Inter', sans-serif;
      margin: 0;
      padding: 30px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    h1 {{
      color: #ff9800;
      font-size: 28px;
      margin-bottom: 5px;
    }}
    p {{
      color: #b0bec5;
      font-size: 14px;
      margin-top: 0;
      margin-bottom: 30px;
    }}
    .mermaid {{
      background: #1e1e1e;
      padding: 30px;
      border-radius: 12px;
      box-shadow: 0 8px 16px rgba(0,0,0,0.5);
      width: 100%;
      max-width: 1200px;
      box-sizing: border-box;
    }}
  </style>
</head>
<body>
  <h1>Factory Layout Flowchart</h1>
  <p>Visual plan for producing {target_name}</p>
  <div class="mermaid">
{markup}
  </div>
</body>
</html>
"""
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    import contextlib

    abs_path = os.path.abspath(html_file)
    with contextlib.suppress(Exception):
        webbrowser.open(f"file://{abs_path}")
    return str(html_file)


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

    # Resolve fuzzy item name if provided
    if args.item:
        from utils.recipe_db import RECIPES

        args.item = _resolve_item_interactive(args.item, set(RECIPES.keys()), label="Target item")

    try:
        plan = generate_production_plan(
            target_item=args.item, target_rate=args.rate, coupons_per_minute=args.coupons, save_file_path=filename
        )
    except Exception as e:
        print(f"Error generating production plan: {e}")
        sys.exit(1)

    # Print output report
    print("\n" + "=" * 55)
    print("=== FACTORY PRODUCTION PLAN ===")
    print("=" * 55)

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
        print(
            f"{step['item']:<28} | {step['recipe_name']:<28} | {step['machine']:<15} | {step['machine_count']:<10.2f} | {status}"
        )

    print("=" * 55)

    if args.draw or args.draw_html:
        from tools.factory_planner import generate_mermaid_flowchart

        chart = generate_mermaid_flowchart(plan["target_item"], plan["target_rate"])
        if args.draw:
            print("\n--- Factory Layout Flowchart (Mermaid) ---")
            print("Copy-paste the block below into a markdown file or view at https://mermaid.live")
            print("```mermaid")
            print(chart)
            print("```")
        if args.draw_html:
            path = _save_flowchart_html(chart, plan["target_item"])
            print(f"\nFlowchart HTML exported to: {path}")


def _run_plan_late_game(args: argparse.Namespace) -> None:
    import math
    import os
    import sys

    from tools.late_game_planner import ALL_RECIPES, generate_late_game_plan

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

    # Resolve fuzzy item names interactively
    valid_items = set(ALL_RECIPES.keys())
    args.item = _resolve_item_interactive(args.item, valid_items, label="Target item")

    sloop_items: set[str] = set()
    for s in args.sloops:
        sloop_items.add(_resolve_item_interactive(s, valid_items, label="Somersloop item"))

    overclock = not args.no_overclock

    try:
        plan = generate_late_game_plan(
            target_item=args.item,
            target_rate=args.rate,
            overclock=overclock,
            sloop_items=sloop_items,
            save_file_path=filename,
            recipe_multiplier=args.recipe_multiplier,
        )
    except Exception as e:
        print(f"Error generating late game plan: {e}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print(f"=== LATE-GAME FACTORY PLAN: {plan['target_item']} @ {plan['target_rate']:.2f}/min ===")
    print("=" * 80)
    print(f"Overclocking (250%): {'ENABLED (uses 3 Shards per machine)' if plan['overclock'] else 'DISABLED'}")
    if plan["sloop_items"]:
        print(f"Somersloop Amplified: {', '.join(plan['sloop_items'])}")
    else:
        print("Somersloop Amplified: NONE")

    if plan["warnings"]:
        print("\n[WARNINGS]")
        for w in plan["warnings"]:
            print(f" - {w}")

    print("\n--- Raw Materials & Dimensional Depot Status ---")
    print(f"{'Raw Resource':<25} | {'Required Rate':<15} | {'Stored in Depot':<15} | {'Depot Status'}")
    print("-" * 75)
    for raw, info in sorted(plan["depot_comparison"].items()):
        status = "OK" if info["stored_qty"] >= info["required_rate"] * 10 else "Low Stored Buffer"
        print(f"{raw:<25} | {info['required_rate']:<15.2f} | {info['stored_qty']:<15d} | {status}")

    from utils.recipe_db import SINK_POINTS

    total_sink_points = 0.0

    print("\n--- Production Steps, Machines & Slugs/Sloops ---")
    print(
        f"{'Output Item':<25} | {'Machine Type':<22} | {'Exact':<6} | {'Build':<5} | {'Shards':<6} | {'Sloops':<6} | {'Max Out':<8} | {'Overflow':<8} | {'Sink Pts/min'}"
    )
    print("-" * 115)
    for step in sorted(plan["steps"], key=lambda x: x["item"]):
        exact_cnt = step["machine_count"]
        build_cnt = math.ceil(exact_cnt)
        shards = build_cnt * step["shards_per_machine"]
        sloops = build_cnt * step["sloops_per_machine"]
        max_out = build_cnt * step["output_per_machine"]
        overflow = max_out - step["rate"]
        pts_each = SINK_POINTS.get(step["item"], 0)
        sink_pts = overflow * pts_each
        total_sink_points += sink_pts

        print(
            f"{step['item']:<25} | {step['machine']:<22} | {exact_cnt:<6.2f} | {build_cnt:<5d} | {shards:<6d} | {sloops:<6d} | {max_out:<8.1f} | {overflow:<8.1f} | {sink_pts:,.0f}"
        )

    print("-" * 115)
    print(
        f"{'TOTALS':<49} | {'':<6} | {'':<5} | {plan['total_shards']:<6d} | {plan['total_sloops']:<6d} | {'':<8} | {'':<8} | {total_sink_points:,.0f} pts/min"
    )

    print("\n--- Energy & Generator Estimations ---")
    gen = plan["fuel_generators"]
    print(f"Total Factory Power Requirement:  {plan['total_power_mw']:.2f} MW")
    print("Equivalent Fuel Generators (250MW standard / 625MW overclocked):")
    print(
        f"  - At 100% clock speed: {math.ceil(gen['generators_needed'] * 2.5 if plan['overclock'] else gen['generators_needed'])} generators"
    )
    print(
        f"  - At 250% clock speed: {math.ceil(gen['generators_needed'] if plan['overclock'] else gen['generators_needed'] / 2.5)} generators"
    )
    print()
    print("Fuel Supply (choose ONE — these are alternatives, not cumulative):")
    print(f"  Option A — Rocket Fuel only:   {gen['rocket_fuel_m3_min']:>8.2f} m³/min")
    print(f"  Option B — Ionized Fuel only:  {gen['ionized_fuel_m3_min']:>8.2f} m³/min")
    print("  (Ionized Fuel is denser — fewer generators needed for the same power.)")

    # --- Build Guide ---
    guide = plan["build_guide"]
    print("\n" + "=" * 80)
    print("=== FACTORY BUILD GUIDE ===")
    print("=" * 80)

    for phase in guide["phases"]:
        print(f"\n  Phase {phase['phase']} · {phase['name']}")
        print(f"  {phase['description']}")
        if phase["depth"] == -1:
            # Raw extraction phase
            print(f"  {'Resource':<25} | {'Required Rate':>14}")
            print(f"  {'-' * 42}")
            for item in phase["items"]:
                print(f"  {item['item']:<25} | {item['rate']:>11.2f}/min")
        else:
            print(f"  {'Item':<25} | {'Machine':<22} | {'Build':>5} | {'Target':>10} | {'Max Out':>10}")
            print(f"  {'-' * 83}")
            for item in phase["items"]:
                print(
                    f"  {item['item']:<25} | {item['machine']:<22} | {item['machine_count']:>5d} | {item['rate']:>7.2f}/min | {item['max_output']:>7.2f}/min"
                )

    if guide["co_location_groups"]:
        print("\n--- Co-locate (shared inputs) ---")
        for g in guide["co_location_groups"]:
            items_str = " + ".join(g["items"])
            print(f"  • {items_str} — both consume {g['shared_input']}")

    if guide["dedicated_items"]:
        print("\n--- Dedicated Factory (multiple consumers) ---")
        for d in guide["dedicated_items"]:
            print(f"  • {d['item']} → feeds {', '.join(d['consumers'])}")

    if guide["inline_items"]:
        print("\n--- Build In-Line (single consumer) ---")
        for il in guide["inline_items"]:
            print(f"  • {il['item']} → only feeds {il['consumer']}")

    print("=" * 80 + "\n")

    if args.draw or args.draw_html:
        from tools.late_game_planner import generate_mermaid_flowchart

        chart = generate_mermaid_flowchart(
            plan["target_item"],
            plan["target_rate"],
            set(),  # schematics check is internal to plan
            plan["sloop_items"],
            plan["overclock"],
            args.recipe_multiplier,
        )
        if args.draw:
            print("\n--- Factory Layout Flowchart (Mermaid) ---")
            print("Copy-paste the block below into a markdown file or view at https://mermaid.live")
            print("```mermaid")
            print(chart)
            print("```")
        if args.draw_html:
            path = _save_flowchart_html(chart, plan["target_item"])
            print(f"\nFlowchart HTML exported to: {path}")


async def _run_status() -> None:
    from temporalio.client import Client

    from utils import config as cfg

    address = cfg.get("temporal.address", "localhost:7233")
    try:
        client = await Client.connect(address)
    except Exception as exc:
        print(f"Error: Could not connect to Temporal at {address}: {exc}")
        sys.exit(1)

    print(f"Connected to Temporal at {address}")
    print("-" * 60)

    try:
        workflows = []
        async for workflow_desc in client.list_workflows("ExecutionStatus = 'Running'"):
            workflows.append(workflow_desc)
    except Exception as exc:
        print(f"Error listing workflows: {exc}")
        sys.exit(1)

    if not workflows:
        print("No workflows are currently running.")
        return

    print(f"{'Workflow ID':<35} | {'Type':<25} | {'Start Time':<20}")
    print("-" * 85)
    for wf in workflows:
        start_time_str = wf.start_time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{wf.id:<35} | {wf.workflow_type:<25} | {start_time_str:<20}")

        # Try to query stats
        try:
            handle = client.get_workflow_handle(wf.id)
            stats = await handle.query("get_stats")
            print("    * Live Stats:")
            for k, v in stats.items():
                print(f"      - {k}: {v}")
        except Exception:
            pass
    print("-" * 85)


async def _run_schedules(args: argparse.Namespace) -> None:
    import argparse as ap

    import schedule_gift_farm

    # Prepare a namespace that matches what schedule_gift_farm expects
    ns = ap.Namespace()
    ns.name = getattr(args, "name", None)
    ns.start = getattr(args, "start", "08:00")
    ns.stop = getattr(args, "stop", "23:00")
    ns.no_stop = getattr(args, "no_stop", False)
    ns.timezone = getattr(args, "timezone", None)
    ns.ammo_per_craft = getattr(args, "ammo_per_craft", 50)
    ns.screenshot_every_cycles = getattr(args, "screenshot_every_cycles", 10)
    ns.interval = getattr(args, "interval", 50.0)

    if args.action == "list":
        ns.name = None
        await schedule_gift_farm.status(ns)
    elif args.action == "status":
        await schedule_gift_farm.status(ns)
    elif args.action == "create":
        await schedule_gift_farm.create(ns)
    elif args.action == "pause":
        await schedule_gift_farm.pause(ns)
    elif args.action == "unpause":
        await schedule_gift_farm.unpause(ns)
    elif args.action == "delete":
        await schedule_gift_farm.delete(ns)


if __name__ == "__main__":
    main()
