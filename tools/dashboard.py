"""
tools/dashboard.py

A lightweight dashboard server for monitoring autonomous satisfactory loops.
Serves a Single Page Application with interactive tabs for:
1. Telemetry stats and SQLite taming metrics.
2. Visual calibration crop gallery.
3. Live power grid and POI visualizer map.
4. Active controls (triggering loops & schedules).
5. Interactive calibration parameters configuration.
6. Factory Production and Late-Game specialized planners.
"""

import contextlib
import http.server
import json
import os
import socketserver
import sqlite3
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tools.map_power import generate_power_map  # noqa: E402

# Global version trackers for save file watching
global_save_version = 0
global_last_modified = ""
global_watcher_active = True


def watch_save_files():
    global global_save_version, global_last_modified, global_watcher_active
    from tools.cli import _find_latest_save_file

    last_path = None
    last_mtime = 0.0

    # Ensure stats directory exists
    stats_dir = Path("stats")
    stats_dir.mkdir(exist_ok=True)

    print("[Watcher] Background Save File Watcher thread started.")
    while global_watcher_active:
        try:
            path = _find_latest_save_file()
            if path:
                mtime = os.path.getmtime(path)
                if path != last_path or mtime != last_mtime:
                    # Save changed!
                    print(f"\n[Watcher] Detected changes to save file: {path}")
                    # Re-run map generation
                    generate_power_map()

                    last_path = path
                    last_mtime = mtime
                    global_save_version += 1
                    global_last_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception as exc:
            print(f"[Watcher Error] {exc}", file=sys.stderr)
        time.sleep(2.0)


def update_config_value(section_name: str, key_name: str, new_val: Any) -> bool:
    """Updates config.toml value keeping existing comments and spacing formatting."""
    try:
        path = Path("config.toml")
        if not path.exists():
            return False
        lines = path.read_text(encoding="utf-8").splitlines()
        in_section = False
        updated = False
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1].strip()
                in_section = current_section == section_name
            elif in_section and "=" in line:
                parts = line.split("=", 1)
                k = parts[0].strip()
                if k == key_name:
                    if isinstance(new_val, bool):
                        v_str = "true" if new_val else "false"
                    elif isinstance(new_val, str):
                        v_str = f'"{new_val}"'
                    else:
                        v_str = str(new_val)
                    lines[idx] = f"{k} = {v_str}"
                    updated = True
                    break
        if updated:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            from utils import config

            config.reload()
            return True
    except Exception:
        pass
    return False


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging to stdout to keep CLI clean
        pass

    def do_GET(self):
        with contextlib.suppress(ConnectionError):
            self._handle_get()

    def _handle_get(self):
        # Serve API: Watcher status (long-polling)
        if self.path.startswith("/api/watch"):
            query = self.path.split("?")[-1] if "?" in self.path else ""
            client_version = 0
            if "version=" in query:
                with contextlib.suppress(ValueError):
                    client_version = int(query.split("version=")[-1].split("&")[0])

            # Wait up to 8 seconds for new save version
            start_time = time.time()
            while time.time() - start_time < 8.0:
                if global_save_version > client_version:
                    break
                time.sleep(0.5)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {
                "version": global_save_version,
                "modified": global_last_modified,
            }
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        # Serve API: Run production / late game factory planner
        if self.path.startswith("/api/planner"):
            query = self.path.split("?")[-1] if "?" in self.path else ""
            params = {}
            for pair in query.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = urllib.parse.unquote_plus(v)

            try:
                raw_item = params.get("item", "Modular Frame")
                rate = float(params.get("rate", "10.0"))
                mode = params.get("mode", "standard")
                overclock = params.get("overclock", "true") == "true"
                sloops_str = params.get("sloops", "")
                recipe_multiplier = float(params.get("recipe_multiplier", "0.75"))

                # Resolve item name case-insensitively and handle acronyms
                from tools.late_game_planner import ALL_RECIPES
                from utils.recipe_db import RECIPES

                def resolve_item(name: str) -> str:
                    if name in ALL_RECIPES:
                        return name
                    for r in ALL_RECIPES:
                        if r.lower() == name.lower():
                            return r
                    mapping = {}
                    for r in ALL_RECIPES:
                        words = [w for w in r.split() if w]
                        if len(words) >= 2:
                            acronym = "".join(w[0].upper() for w in words if w[0].isalnum())
                            if acronym:
                                mapping[acronym] = r
                    if name.upper() in mapping:
                        return mapping[name.upper()]
                    return name

                item = resolve_item(raw_item)
                sloops = [resolve_item(s.strip()) for s in sloops_str.split(",") if s.strip()]

                # Auto-upgrade to late_game if the item is not in standard recipes
                if item not in RECIPES and item in ALL_RECIPES:
                    mode = "late_game"

                from tools.cli import _find_latest_save_file

                save_path = _find_latest_save_file()
                if not save_path:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "No save file found"}).encode("utf-8"))
                    return

                if mode == "late_game":
                    from tools.late_game_planner import generate_late_game_plan
                    from tools.late_game_planner import generate_mermaid_flowchart as gen_flowchart_lg

                    plan = generate_late_game_plan(item, rate, overclock, set(sloops), save_path, recipe_multiplier)
                    flowchart = gen_flowchart_lg(item, rate, set(), set(sloops), overclock, recipe_multiplier)
                else:
                    from tools.factory_planner import generate_mermaid_flowchart as gen_flowchart_std
                    from tools.factory_planner import generate_production_plan

                    plan = generate_production_plan(item, rate, None, save_path)
                    flowchart = gen_flowchart_std(item, rate)

                if "sloop_items" in plan and isinstance(plan["sloop_items"], set):
                    plan["sloop_items"] = sorted(list(plan["sloop_items"]))

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response = {"plan": plan, "flowchart": flowchart}
                self.wfile.write(json.dumps(response).encode("utf-8"))
            except Exception as e:
                import traceback

                print(f"[Dashboard Planner Exception] {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # Serve API: Get config options
        if self.path == "/api/config/get":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            from utils import config

            config.reload()
            data = {
                "version": {
                    "default_threshold": config.get("vision.default_threshold", 0.8),
                },
                "taming": {
                    "feed_wait_seconds": config.get("taming.feed_wait_seconds", 30.0),
                },
                "combat": {
                    "low_health_threshold": config.get("combat.low_health_threshold", 40),
                },
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # Serve API: Update config option
        if self.path.startswith("/api/config/update"):
            query = self.path.split("?")[-1] if "?" in self.path else ""
            params = {}
            for pair in query.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v

            success = False
            if "vision.default_threshold" in params:
                success = update_config_value("vision", "default_threshold", float(params["vision.default_threshold"]))
            if "taming.feed_wait_seconds" in params:
                success = update_config_value("taming", "feed_wait_seconds", float(params["taming.feed_wait_seconds"]))
            if "combat.low_health_threshold" in params:
                success = update_config_value(
                    "combat", "low_health_threshold", int(params["combat.low_health_threshold"])
                )

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode("utf-8"))
            return

        # Serve API: Trigger active workflows
        if self.path.startswith("/api/workflow/trigger"):
            query = self.path.split("?")[-1] if "?" in self.path else ""
            params = {}
            for pair in query.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v

            wf_type = params.get("type", "")
            success = False
            message = ""

            if wf_type:
                threading.Thread(target=lambda: self._trigger_workflow_async(wf_type, params), daemon=True).start()
                success = True
                message = f"Asynchronously triggered loop for {wf_type}."

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "message": message}).encode("utf-8"))
            return

        # Serve API: Manage schedules actions
        if self.path.startswith("/api/schedules/action"):
            query = self.path.split("?")[-1] if "?" in self.path else ""
            params = {}
            for pair in query.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v

            action = params.get("action", "")
            name = params.get("name", "daily")
            success = False
            message = ""

            if action in ("pause", "unpause"):
                threading.Thread(target=lambda: self._run_schedule_action_async(action, name), daemon=True).start()
                success = True
                message = f"Triggered schedule {action} for {name}."

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "message": message}).encode("utf-8"))
            return

        # Serve API: Stats & SQLite metrics
        if self.path == "/api/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = self._get_stats_data()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # Serve API: Live Temporal Audit Log
        if self.path == "/api/audit":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = self._get_temporal_audit_log()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # Serve API: Screenshots List
        if self.path == "/api/screenshots":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = self._get_screenshots_list()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # Serve API: Live Map HTML
        if self.path == "/api/map":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = self._get_map_html()
            self.wfile.write(html.encode("utf-8"))
            return

        # Serve static screenshots from debug_screenshots/
        if self.path.startswith("/screenshots/"):
            filename = self.path.split("/")[-1]
            filepath = Path("debug_screenshots") / filename
            if filepath.exists() and filepath.suffix == ".png":
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                with open(filepath, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(404, "File not found")
            return

        # Default: Serve Dashboard SPA HTML
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        html = self._get_dashboard_html()
        self.wfile.write(html.encode("utf-8"))

    def _trigger_workflow_async(self, wf_type: str, params: dict):
        import asyncio

        from temporalio.client import Client

        from workflows.depot_coal import DepotCoalToStorageWorkflow
        from workflows.exploration import ExplorationWorkflow
        from workflows.gift_farm import GiftFarmWorkflow
        from workflows.template_orchestration import TemplateOrchestrationWorkflow

        async def run():
            try:
                client = await Client.connect("localhost:7233")
                if wf_type == "calibration":
                    target = params.get("target", "hud")
                    res = params.get("resolution", "2560x1440")
                    await client.start_workflow(
                        TemplateOrchestrationWorkflow.run,
                        args=[target, res],
                        id="calibration-workflow-run",
                        task_queue="satisfactory-bot",
                    )
                elif wf_type == "exploration":
                    await client.start_workflow(
                        ExplorationWorkflow.run,
                        args=[None, False, False],
                        id="exploration-run",
                        task_queue="satisfactory-bot",
                    )
                elif wf_type == "depot_coal":
                    await client.start_workflow(
                        DepotCoalToStorageWorkflow.run,
                        args=[15.0, None, 5],
                        id="depot-coal-run",
                        task_queue="satisfactory-bot",
                    )
                elif wf_type == "gift_farm":
                    await client.start_workflow(
                        GiftFarmWorkflow.run,
                        args=[200, 50, 10, 50.0],
                        id="gift-farm-run",
                        task_queue="satisfactory-bot",
                    )
            except Exception as e:
                print(f"[Dashboard Async Workflow Error] {e}", file=sys.stderr)

        asyncio.run(run())

    def _run_schedule_action_async(self, action: str, name: str):
        import argparse
        import asyncio

        import schedule_gift_farm

        async def run():
            try:
                args = argparse.Namespace(name=name)
                if action == "pause":
                    await schedule_gift_farm.pause(args)
                elif action == "unpause":
                    await schedule_gift_farm.unpause(args)
            except Exception as e:
                print(f"[Dashboard Async Schedule Error] {e}", file=sys.stderr)

        asyncio.run(run())

    def _get_stats_data(self) -> dict:
        db_path = Path("stats") / "gift_history.db"
        gift_summary: dict[str, Any] = {"total_checks": 0, "collected_count": 0, "by_doggo": {}}
        if db_path.exists():
            try:
                with sqlite3.connect(db_path) as conn:
                    cur = conn.execute("SELECT COUNT(*), SUM(collected) FROM gift_checks")
                    row = cur.fetchone()
                    if row:
                        gift_summary["total_checks"] = row[0]
                        gift_summary["collected_count"] = row[1] or 0

                    cur = conn.execute("SELECT doggo, COUNT(*), SUM(collected) FROM gift_checks GROUP BY doggo")
                    for r in cur.fetchall():
                        gift_summary["by_doggo"][r[0]] = {"checks": r[1], "collected": r[2] or 0}
            except Exception:
                pass

        stats_dir = Path("stats")
        recent_runs = []
        if stats_dir.exists():
            try:
                for f in sorted(stats_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
                    with open(f, encoding="utf-8") as file:
                        recent_runs.append(json.load(file))
            except Exception:
                pass

        return {
            "gift_summary": gift_summary,
            "recent_runs": recent_runs,
        }

    def _get_temporal_audit_log(self) -> list[dict]:
        import asyncio

        from temporalio.client import Client

        async def run():
            items = []
            try:
                client = await Client.connect("localhost:7233")
                async for handle in client.list_workflows(limit=15):
                    try:
                        desc = await handle.describe()
                        status_str = desc.status.name if hasattr(desc.status, "name") else str(desc.status)
                        start_str = desc.start_time.strftime("%Y-%m-%d %H:%M:%S") if desc.start_time else ""
                        close_str = desc.close_time.strftime("%Y-%m-%d %H:%M:%S") if desc.close_time else "Active"

                        identity = "Unknown Principal"
                        if hasattr(desc, "raw_info") and hasattr(desc.raw_info, "execution_info"):
                            raw_identity = getattr(desc.raw_info.execution_info, "identity", None)
                            if raw_identity:
                                identity = raw_identity

                        items.append(
                            {
                                "id": desc.id,
                                "type": desc.workflow_type,
                                "status": status_str,
                                "start_time": start_str,
                                "close_time": close_str,
                                "principal": identity,
                            }
                        )
                    except Exception:
                        pass
            except Exception as e:
                print(f"[Dashboard Audit Log Error] {e}", file=sys.stderr)
            return items

        return asyncio.run(run())

    def _get_screenshots_list(self) -> list[dict]:
        screenshot_dir = Path("debug_screenshots")
        if not screenshot_dir.exists():
            return []
        try:
            items = []
            for f in sorted(screenshot_dir.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)[:30]:
                mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                items.append({"name": f.name, "timestamp": mtime})
            return items
        except Exception:
            return []

    def _get_map_html(self) -> str:
        try:
            result = generate_power_map()
            if not result:
                return "<h3>Error: Power map generation returned no data. Ensure a save file exists.</h3>"

            from tools.cli import _save_map_html

            _save_map_html(result["map"], result["pois"], open_browser=False)

            html_path = Path("stats") / "reachable_power_map.html"
            if html_path.exists():
                return html_path.read_text(encoding="utf-8")
        except Exception as exc:
            return f"<h3>Error generating map: {exc}</h3>"
        return "<h3>Reachable power map file not found.</h3>"

    def _get_dashboard_html(self) -> str:
        return """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Satisfactory gameplay Dashboard</title>
  <!-- Load Mermaid dynamically for flowchart rendering -->
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <script>
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      securityLevel: 'loose',
      maxTextSize: 150000,
      maxEdges: 2000,
      flowchart: { useMaxWidth: false, htmlLabels: true }
    });
  </script>
  <style>
    body {
      background-color: #121212;
      color: #ffffff;
      font-family: 'Inter', sans-serif;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      height: 100vh;
    }
    header {
      background-color: #1e1e1e;
      border-bottom: 2px solid #ff9800;
      padding: 15px 30px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    header h1 {
      margin: 0;
      color: #ff9800;
      font-size: 22px;
      font-weight: 600;
    }
    .tabs {
      display: flex;
      background-color: #1e1e1e;
      border-bottom: 1px solid #37474f;
      padding: 0 30px;
    }
    .tab {
      padding: 15px 25px;
      cursor: pointer;
      color: #b0bec5;
      border-bottom: 3px solid transparent;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s;
    }
    .tab:hover {
      color: #fff;
    }
    .tab.active {
      color: #ff9800;
      border-bottom-color: #ff9800;
    }
    .content-area {
      flex: 1;
      padding: 30px;
      overflow-y: auto;
      box-sizing: border-box;
    }
    .tab-content {
      display: none;
    }
    .tab-content.active {
      display: block;
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 30px;
      margin-bottom: 30px;
    }
    .card {
      background-color: #1e1e1e;
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 4px 8px rgba(0,0,0,0.3);
      margin-bottom: 20px;
    }
    .card h2 {
      margin-top: 0;
      color: #ff9800;
      font-size: 16px;
      border-bottom: 1px solid #37474f;
      padding-bottom: 10px;
    }
    .metric {
      font-size: 32px;
      font-weight: 700;
      color: #00e676;
      margin: 10px 0;
    }
    .metric-sub {
      color: #90a4ae;
      font-size: 13px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
    }
    th, td {
      text-align: left;
      padding: 10px;
      border-bottom: 1px solid #37474f;
      font-size: 13px;
    }
    th {
      color: #ff9800;
      font-weight: 600;
    }
    .gallery {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 20px;
    }
    .gallery-item {
      background-color: #263238;
      border-radius: 6px;
      overflow: hidden;
      border: 1px solid #37474f;
      display: flex;
      flex-direction: column;
    }
    .gallery-item img {
      width: 100%;
      height: 120px;
      object-fit: cover;
      cursor: pointer;
    }
    .gallery-info {
      padding: 8px;
      font-size: 11px;
      color: #cfd8dc;
      text-align: center;
      background-color: #1e1e1e;
    }
    iframe {
      width: 100%;
      height: 80vh;
      border: none;
      border-radius: 8px;
      background-color: #0d0d0d;
    }
    .btn {
      background-color: #ff9800;
      border: none;
      padding: 10px 20px;
      border-radius: 4px;
      color: #000;
      font-weight: bold;
      cursor: pointer;
      margin-right: 10px;
      transition: background-color 0.2s;
    }
    .btn:hover {
      background-color: #ffd54f;
    }
    .btn-secondary {
      background-color: #37474f;
      color: #fff;
    }
    .btn-secondary:hover {
      background-color: #455a64;
    }
    .control-group {
      margin-bottom: 20px;
    }
    .control-label {
      font-size: 14px;
      font-weight: 500;
      margin-bottom: 8px;
      color: #b0bec5;
    }
    .slider-container {
      display: flex;
      align-items: center;
      gap: 15px;
      margin-bottom: 15px;
    }
    .slider-container input[type="range"] {
      flex: 1;
    }
    .slider-value {
      font-weight: bold;
      color: #00e5ff;
      width: 50px;
    }
    .form-row {
      display: flex;
      gap: 20px;
      margin-bottom: 15px;
      align-items: center;
    }
    .form-row {
      display: flex;
      gap: 20px;
      margin-bottom: 15px;
      align-items: center;
    }
    .form-group {
      display: flex;
      flex-direction: column;
      flex: 1;
    }
    .form-group label {
      font-size: 12px;
      color: #90a4ae;
      margin-bottom: 5px;
    }
    .form-group input, .form-group select {
      background-color: #263238;
      border: 1px solid #37474f;
      border-radius: 4px;
      padding: 10px;
      color: #fff;
      font-size: 14px;
    }
    .mermaid {
      background-color: #0a0a0a;
      border: 1px solid #37474f;
      border-radius: 8px;
      padding: 20px;
      overflow-x: auto;
      text-align: center;
    }
  </style>
</head>
<body>
  <header>
    <h1>Satisfactory Autonomous Gameplay Dashboard</h1>
    <span style="color: #00e5ff; font-size: 12px;">Local Server Active</span>
  </header>

  <div class="tabs">
    <div class="tab active" onclick="switchTab('telemetry')">📊 Telemetry & Stats</div>
    <div class="tab" onclick="switchTab('gallery')">🖼️ Screenshot Gallery</div>
    <div class="tab" onclick="switchTab('map-view')">🗺️ Live Power Grid Map</div>
    <div class="tab" onclick="switchTab('controls')">🎮 Active Controls</div>
    <div class="tab" onclick="switchTab('calibration')">🎛️ Calibration Wizard</div>
    <div class="tab" onclick="switchTab('planner-view')">🏭 Factory Planner</div>
  </div>

  <div class="content-area">
    <!-- Telemetry Tab -->
    <div id="telemetry" class="tab-content active">
      <div class="grid-2">
        <div class="card">
          <h2>Doggo Gift Collecting Summary</h2>
          <div style="display: flex; justify-content: space-around; text-align: center;">
            <div>
              <div class="metric" id="total-checks">0</div>
              <div class="metric-sub">Total Checks</div>
            </div>
            <div>
              <div class="metric" id="total-gifts" style="color: #ffab00;">0</div>
              <div class="metric-sub">Gifts Transferred</div>
            </div>
            <div>
              <div class="metric" id="efficiency">0%</div>
              <div class="metric-sub">Roll Hit Rate</div>
            </div>
          </div>
        </div>
        <div class="card">
          <h2>Roster of Tamed Lizard Doggos</h2>
          <table id="doggo-table">
            <thead>
              <tr>
                <th>Lizard Doggo Name</th>
                <th>Checks Logged</th>
                <th>Gifts Collected</th>
              </tr>
            </thead>
            <tbody>
              <tr><td colspan="3" style="text-align: center; color: #90a4ae;">No doggos tamed yet.</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h2>Recent Workflow Runs History</h2>
        <table id="runs-table">
          <thead>
            <tr>
              <th>Workflow Type</th>
              <th>Saved At</th>
              <th>Stats Details</th>
            </tr>
          </thead>
          <tbody>
            <tr><td colspan="3" style="text-align: center; color: #90a4ae;">No recent runs.</td></tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <h2>Live Temporal Audit Logs & Principal Initiators</h2>
        <table id="audit-table">
          <thead>
            <tr>
              <th>Workflow ID</th>
              <th>Workflow Type</th>
              <th>Status</th>
              <th>Started At</th>
              <th>Closed At</th>
              <th>Initiator (Principal)</th>
            </tr>
          </thead>
          <tbody>
            <tr><td colspan="6" style="text-align: center; color: #90a4ae;">No audits logged. Ensure Temporal is running.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Screenshot Gallery Tab -->
    <div id="gallery" class="tab-content">
      <div class="gallery" id="gallery-container">
        <!-- Screenshots injected here -->
      </div>
    </div>

    <!-- Map View Tab -->
    <div id="map-view" class="tab-content">
      <iframe src="" id="map-iframe"></iframe>
    </div>

    <!-- Active Controls Tab -->
    <div id="controls" class="tab-content">
      <div class="card">
        <h2>Temporal Loops & Workflows Controls</h2>
        <div class="control-group">
          <div class="control-label">Visual Calibration Loop</div>
          <button class="btn" onclick="triggerWorkflow('calibration')">Trigger Calibration Run</button>
        </div>
        <div class="control-group">
          <div class="control-label">Exploration Loop (Movement Budget)</div>
          <button class="btn" onclick="triggerWorkflow('exploration')">Start Exploration loop</button>
        </div>
        <div class="control-group">
          <div class="control-label">Dimensional Depot Coal Loop</div>
          <button class="btn" onclick="triggerWorkflow('depot_coal')">Start Depot Coal loop</button>
        </div>
        <div class="control-group">
          <div class="control-label">Autonomous Gift Farm Loop</div>
          <button class="btn" onclick="triggerWorkflow('gift_farm')">Start Gift Farm Loop</button>
        </div>
      </div>

      <div class="card">
        <h2>Schedule Actions Management (Always-On Windows)</h2>
        <div class="control-group">
          <div class="control-label">Taming Window Schedule [daily]</div>
          <button class="btn" onclick="triggerScheduleAction('pause')">Pause Schedule</button>
          <button class="btn btn-secondary" onclick="triggerScheduleAction('unpause')">Resume/Unpause Schedule</button>
        </div>
      </div>
    </div>

    <!-- Calibration Wizard Tab -->
    <div id="calibration" class="tab-content">
      <div class="card">
        <h2>Interactive Configuration parameters Adjustments</h2>
        <div class="control-group">
          <div class="control-label">Vision Default Threshold (confidence matching)</div>
          <div class="slider-container">
            <input type="range" id="threshold-slider" min="0.5" max="0.99" step="0.01" onchange="updateConfigOption('vision.default_threshold', this.value)">
            <span class="slider-value" id="threshold-val">0.80</span>
          </div>
        </div>
        <div class="control-group">
          <div class="control-label">Wait duration between taming feeds (seconds)</div>
          <div class="slider-container">
            <input type="range" id="feed-slider" min="5" max="120" step="5" onchange="updateConfigOption('taming.feed_wait_seconds', this.value)">
            <span class="slider-value" id="feed-val">30</span>
          </div>
        </div>
        <div class="control-group">
          <div class="control-label">Retreat Low Health Threshold (HP)</div>
          <div class="slider-container">
            <input type="range" id="health-slider" min="10" max="90" step="5" onchange="updateConfigOption('combat.low_health_threshold', this.value)">
            <span class="slider-value" id="health-val">40</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Factory Planner Tab -->
    <div id="planner-view" class="tab-content">
      <div class="card">
        <h2>Production Optimization Calculator</h2>
        <div class="form-row">
          <div class="form-group">
            <label for="plan-item">Output Target Item</label>
            <select id="plan-item">
              <option value="Modular Frame">Modular Frame</option>
              <option value="Heavy Modular Frame">Heavy Modular Frame</option>
              <option value="Thermal Propulsion Rocket">Thermal Propulsion Rocket</option>
              <option value="Ballistic Warp Drive">Ballistic Warp Drive</option>
              <option value="Superposition Oscillator">Superposition Oscillator</option>
              <option value="Nuclear Pasta">Nuclear Pasta</option>
              <option value="Magnetic Field Generator">Magnetic Field Generator</option>
            </select>
          </div>
          <div class="form-group">
            <label for="plan-rate">Desired Output Rate (items/min)</label>
            <input type="number" id="plan-rate" value="10" min="0.1" step="0.5">
          </div>
          <div class="form-group">
            <label for="plan-mode">Planner Mode Selection</label>
            <select id="plan-mode" onchange="togglePlannerModeInputs()">
              <option value="standard">Standard Production</option>
              <option value="late_game">Late-Game Specialized Scaling</option>
            </select>
          </div>
        </div>

        <div id="late-game-inputs" style="display: none; border-top: 1px solid #37474f; padding-top: 15px; margin-top: 15px;">
          <div class="form-row">
            <div class="form-group">
              <label for="plan-sloops">Somersloop Amplify Items (comma separated names)</label>
              <input type="text" id="plan-sloops" placeholder="e.g. Superposition Oscillator, Dark Matter Crystal">
            </div>
            <div class="form-group" style="flex: 0; min-width: 150px;">
              <label for="plan-mult">Recipe Multiplier</label>
              <input type="number" id="plan-mult" value="0.75" min="0.05" max="2.0" step="0.05">
            </div>
            <div class="form-group" style="flex: 0; min-width: 120px; text-align: center;">
              <label for="plan-overclock">Overclock (250%)</label>
              <input type="checkbox" id="plan-overclock" checked style="width: 20px; height: 20px; margin: 10px auto 0 auto;">
            </div>
          </div>
        </div>

        <div style="margin-top: 15px;">
          <button class="btn" onclick="calculateFactoryPlan()">Calculate Optimized Plan</button>
        </div>
      </div>

      <div id="planner-results" style="display: none;">
        <!-- Warnings Card -->
        <div id="planner-warnings-card" class="card" style="display: none; border-left: 5px solid #ff1744;">
          <h2 style="color: #ff1744;">Recipe Research Warnings</h2>
          <ul id="planner-warnings-list" style="margin-top: 10px; padding-left: 20px; color: #ff8a80; font-size: 13px;"></ul>
        </div>

        <!-- Metrics Grid -->
        <div id="planner-metrics-card" class="card" style="display: none;">
          <h2>Power & Shards Requirements Summary</h2>
          <div style="display: flex; justify-content: space-around; text-align: center;">
            <div>
              <div class="metric" id="plan-total-power" style="color: #00e5ff;">0 MW</div>
              <div class="metric-sub">Estimated Peak Power</div>
            </div>
            <div>
              <div class="metric" id="plan-total-shards" style="color: #ffd600;">0</div>
              <div class="metric-sub">Power Shards Needed</div>
            </div>
            <div>
              <div class="metric" id="plan-total-sloops" style="color: #d500f9;">0</div>
              <div class="metric-sub">Somersloops Required</div>
            </div>
          </div>
        </div>

        <div class="grid-2">
          <!-- Steps Table -->
          <div class="card">
            <h2>Detailed Production Steps</h2>
            <table id="plan-steps-table">
              <thead>
                <tr>
                  <th>Item Produced</th>
                  <th>Recipe</th>
                  <th>Machine & Qty</th>
                  <th>Rate</th>
                </tr>
              </thead>
              <tbody></tbody>
            </table>
          </div>

          <!-- Raw Materials Table -->
          <div class="card">
            <h2>Raw Node Materials Required</h2>
            <table id="plan-raw-table">
              <thead>
                <tr>
                  <th>Raw Resource Name</th>
                  <th>Required Rate</th>
                </tr>
              </thead>
              <tbody></tbody>
            </table>
          </div>
        </div>

        <!-- Factory Build Guide (Phases) -->
        <div class="card" id="plan-build-guide-card" style="display: none;">
          <h2>🏭 Factory Build Guide (Phases)</h2>
          <div id="plan-build-guide" style="margin-top: 15px;"></div>
        </div>

        <!-- Mermaid Flowchart Visualizer -->
        <div class="card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <h2 style="margin: 0;">Visual Production Layout Flowchart</h2>
            <div style="display: flex; gap: 5px;">
              <button onclick="zoomFlowchart(0.15)" style="padding: 4px 8px; font-size: 12px; background: #333; color: #fff; border: 1px solid #555; border-radius: 4px; cursor: pointer;">🔍 Zoom In</button>
              <button onclick="zoomFlowchart(-0.15)" style="padding: 4px 8px; font-size: 12px; background: #333; color: #fff; border: 1px solid #555; border-radius: 4px; cursor: pointer;">🔍 Zoom Out</button>
              <button onclick="zoomFlowchart(0)" style="padding: 4px 8px; font-size: 12px; background: #333; color: #fff; border: 1px solid #555; border-radius: 4px; cursor: pointer;">Reset</button>
            </div>
          </div>
          <div id="flowchart-wrapper" style="width: 100%; height: 600px; overflow: auto; border: 1px solid #333; background: #151515; border-radius: 4px; position: relative; cursor: grab;">
            <div id="flowchart-container" style="transform-origin: top left; padding: 20px;"></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    function showNotification(text, success=true) {
      const banner = document.createElement('div');
      banner.style.position = 'fixed';
      banner.style.bottom = '20px';
      banner.style.right = '20px';
      banner.style.backgroundColor = success ? '#00e676' : '#ff1744';
      banner.style.color = '#000';
      banner.style.padding = '10px 20px';
      banner.style.borderRadius = '4px';
      banner.style.fontWeight = 'bold';
      banner.style.zIndex = '1000';
      banner.style.fontFamily = 'sans-serif';
      banner.textContent = text;
      document.body.appendChild(banner);
      setTimeout(() => banner.remove(), 4000);
    }

    async function triggerWorkflow(type) {
      try {
        const res = await fetch(`/api/workflow/trigger?type=${type}`);
        const data = await res.json();
        if (data.success) {
          showNotification(data.message);
        } else {
          showNotification('Failed to trigger workflow', false);
        }
      } catch(e) {
        showNotification('Connection error', false);
      }
    }

    async function triggerScheduleAction(action) {
      try {
        const res = await fetch(`/api/schedules/action?action=${action}&name=daily`);
        const data = await res.json();
        if (data.success) {
          showNotification(data.message);
        } else {
          showNotification('Failed to perform schedule action', false);
        }
      } catch(e) {
        showNotification('Connection error', false);
      }
    }

    async function loadConfig() {
      try {
        const res = await fetch('/api/config/get');
        const data = await res.json();

        document.getElementById('threshold-slider').value = data.version.default_threshold;
        document.getElementById('threshold-val').textContent = data.version.default_threshold;

        document.getElementById('feed-slider').value = data.taming.feed_wait_seconds;
        document.getElementById('feed-val').textContent = data.taming.feed_wait_seconds;

        document.getElementById('health-slider').value = data.combat.low_health_threshold;
        document.getElementById('health-val').textContent = data.combat.low_health_threshold;
      } catch (e) {
        console.error('Failed to load config options:', e);
      }
    }

    async function updateConfigOption(key, value) {
      if (key === 'vision.default_threshold') document.getElementById('threshold-val').textContent = value;
      if (key === 'taming.feed_wait_seconds') document.getElementById('feed-val').textContent = value;
      if (key === 'combat.low_health_threshold') document.getElementById('health-val').textContent = value;

      try {
        const res = await fetch(`/api/config/update?${key}=${value}`);
        const data = await res.json();
        if (data.success) {
          showNotification('Updated config.toml successfully.');
        } else {
          showNotification('Failed to update config.toml', false);
        }
      } catch (e) {
        showNotification('Connection error updating config.toml', false);
      }
    }

    function togglePlannerModeInputs() {
      const mode = document.getElementById('plan-mode').value;
      const lateGameDiv = document.getElementById('late-game-inputs');
      lateGameDiv.style.display = mode === 'late_game' ? 'block' : 'none';
    }

    async function calculateFactoryPlan() {
      const item = document.getElementById('plan-item').value;
      const rate = document.getElementById('plan-rate').value;
      const mode = document.getElementById('plan-mode').value;
      const overclock = document.getElementById('plan-overclock').checked;
      const sloops = document.getElementById('plan-sloops').value;
      const recipe_multiplier = document.getElementById('plan-mult').value;

      try {
        showNotification('Running mathematical recipe optimizations...');
        const res = await fetch(`/api/planner?item=${encodeURIComponent(item)}&rate=${rate}&mode=${mode}&overclock=${overclock}&sloops=${encodeURIComponent(sloops)}&recipe_multiplier=${recipe_multiplier}`);
        const data = await res.json();

        if (data.error) {
          showNotification(data.error, false);
          return;
        }

        const plan = data.plan;
        document.getElementById('planner-results').style.display = 'block';

        // Warnings
        const warnCard = document.getElementById('planner-warnings-card');
        const warnList = document.getElementById('planner-warnings-list');
        warnList.innerHTML = '';
        if (plan.warnings && plan.warnings.length > 0) {
          warnCard.style.display = 'block';
          plan.warnings.forEach(w => {
            const li = document.createElement('li');
            li.textContent = w;
            warnList.appendChild(li);
          });
        } else {
          warnCard.style.display = 'none';
        }

        // Metrics (power, shards)
        const metricsCard = document.getElementById('planner-metrics-card');
        if (mode === 'late_game') {
          metricsCard.style.display = 'block';
          document.getElementById('plan-total-power').textContent = Math.round(plan.total_power_mw) + ' MW';
          document.getElementById('plan-total-shards').textContent = plan.total_shards;
          document.getElementById('plan-total-sloops').textContent = plan.total_sloops;
        } else {
          metricsCard.style.display = 'none';
        }

        // Steps
        const stepsBody = document.querySelector('#plan-steps-table tbody');
        stepsBody.innerHTML = '';
        plan.steps.forEach(step => {
          const row = document.createElement('tr');
          const status = step.unlocked ? '' : ' <span style="color:#ff1744; font-size:10px;">[LOCKED]</span>';
          row.innerHTML = `
            <td><b>${step.item}</b>${status}</td>
            <td>${step.recipe_name}</td>
            <td>${step.machine} x${step.machine_count.toFixed(2)}</td>
            <td>${step.rate.toFixed(1)}/min</td>
          `;
          stepsBody.appendChild(row);
        });

        // Raw materials
        const rawBody = document.querySelector('#plan-raw-table tbody');
        rawBody.innerHTML = '';
        Object.entries(plan.raw_materials).forEach(([rawItem, rawRate]) => {
          const row = document.createElement('tr');
          row.innerHTML = `<td><b>${rawItem}</b></td><td>${rawRate.toFixed(1)}/min</td>`;
          rawBody.appendChild(row);
        });

        // Build Guide (Phases)
        const buildGuideCard = document.getElementById('plan-build-guide-card');
        const buildGuideContainer = document.getElementById('plan-build-guide');

        if (plan.build_guide && plan.build_guide.phases && plan.build_guide.phases.length > 0) {
          buildGuideCard.style.display = 'block';
          let html = '';

          plan.build_guide.phases.forEach(phase => {
            html += `<div style="margin-bottom: 20px; padding: 15px; border-left: 4px solid #d500f9; background: #1c1c1c; border-radius: 4px;">`;
            html += `<h3 style="margin-top: 0; color: #d500f9;">Phase ${phase.phase} · ${phase.name}</h3>`;
            html += `<p style="color: #bbb; font-size: 14px;">${phase.description}</p>`;

            if (phase.depth === -1) {
              // Raw extraction
              html += `<table style="width: 100%; border-collapse: collapse; margin-top: 10px;">`;
              html += `<thead><tr style="border-bottom: 1px solid #333;"><th style="text-align: left; padding: 8px 0;">Resource</th><th style="text-align: right; padding: 8px 0;">Required Rate</th></tr></thead>`;
              html += `<tbody>`;
              phase.items.forEach(item => {
                html += `<tr style="border-bottom: 1px solid #252525;"><td style="padding: 8px 0;"><b>${item.item}</b></td><td style="text-align: right; padding: 8px 0;">${item.rate.toFixed(2)}/min</td></tr>`;
              });
              html += `</tbody></table>`;
            } else {
              // Standard production phase
              html += `<table style="width: 100%; border-collapse: collapse; margin-top: 10px;">`;
              html += `<thead><tr style="border-bottom: 1px solid #333;"><th style="text-align: left; padding: 8px 0;">Item</th><th style="text-align: left; padding: 8px 0;">Machine</th><th style="text-align: center; padding: 8px 0;">Build</th><th style="text-align: right; padding: 8px 0;">Target Rate</th><th style="text-align: right; padding: 8px 0;">Max Output</th></tr></thead>`;
              html += `<tbody>`;
              phase.items.forEach(item => {
                html += `<tr style="border-bottom: 1px solid #252525;">`;
                html += `<td style="padding: 8px 0;"><b>${item.item}</b></td>`;
                html += `<td style="padding: 8px 0; color: #00e5ff;">${item.machine}</td>`;
                html += `<td style="text-align: center; padding: 8px 0; color: #ffd600;">${item.machine_count}</td>`;
                html += `<td style="text-align: right; padding: 8px 0;">${item.rate.toFixed(2)}/min</td>`;
                html += `<td style="text-align: right; padding: 8px 0; color: #00e676;">${item.max_output.toFixed(2)}/min</td>`;
                html += `</tr>`;
              });
              html += `</tbody></table>`;
            }
            html += `</div>`;
          });

          // Co-locate groups
          if (plan.build_guide.co_location_groups && plan.build_guide.co_location_groups.length > 0) {
            html += `<div style="margin-top: 20px; padding: 15px; background: #251025; border-radius: 4px; border: 1px dashed #d500f9;">`;
            html += `<h4 style="margin-top: 0; color: #d500f9;">🔗 Co-locate (Shared Inputs)</h4>`;
            html += `<ul style="margin: 0; padding-left: 20px;">`;
            plan.build_guide.co_location_groups.forEach(g => {
              html += `<li style="margin-bottom: 5px;"><b>${g.items.join(' + ')}</b> — both consume <b>${g.shared_input}</b></li>`;
            });
            html += `</ul></div>`;
          }

          // Dedicated items
          if (plan.build_guide.dedicated_items && plan.build_guide.dedicated_items.length > 0) {
            html += `<div style="margin-top: 15px; padding: 15px; background: #1a1a2e; border-radius: 4px; border: 1px dashed #00e5ff;">`;
            html += `<h4 style="margin-top: 0; color: #00e5ff;">⚙️ Dedicated Factory (Multiple Consumers)</h4>`;
            html += `<ul style="margin: 0; padding-left: 20px;">`;
            plan.build_guide.dedicated_items.forEach(d => {
              html += `<li style="margin-bottom: 5px;"><b>${d.item}</b> &rarr; feeds <b>${d.consumers.join(', ')}</b></li>`;
            });
            html += `</ul></div>`;
          }

          // Inline items
          if (plan.build_guide.inline_items && plan.build_guide.inline_items.length > 0) {
            html += `<div style="margin-top: 15px; padding: 15px; background: #1a2e1a; border-radius: 4px; border: 1px dashed #00e676;">`;
            html += `<h4 style="margin-top: 0; color: #00e676;">📦 Build In-Line (Single Consumer)</h4>`;
            html += `<ul style="margin: 0; padding-left: 20px;">`;
            plan.build_guide.inline_items.forEach(il => {
              html += `<li style="margin-bottom: 5px;"><b>${il.item}</b> &rarr; only feeds <b>${il.consumer}</b></li>`;
            });
            html += `</ul></div>`;
          }

          buildGuideContainer.innerHTML = html;
        } else {
          buildGuideCard.style.display = 'none';
        }

        // Render flowchart visualizer dynamically using Mermaid
        const container = document.getElementById('flowchart-container');
        container.innerHTML = `<div class="mermaid">${data.flowchart}</div>`;
        mermaid.init(undefined, container.querySelectorAll('.mermaid'));

        showNotification('Factory layout plan optimized and visualised.');
      } catch (e) {
        showNotification('Connection error fetching planner results', false);
      }
    }

    function switchTab(tabId) {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      const tabs = Array.from(document.querySelectorAll('.tab'));
      const textMap = {
        'telemetry': 'Telemetry',
        'gallery': 'Screenshot',
        'map-view': 'Power Grid',
        'controls': 'Active Controls',
        'calibration': 'Calibration',
        'planner-view': 'Factory Planner'
      };
      const clickedTab = tabs.find(t => t.textContent.includes(textMap[tabId]));
      if (clickedTab) clickedTab.classList.add('active');

      const content = document.getElementById(tabId);
      if (content) content.classList.add('active');

      if (tabId === 'map-view') {
        const iframe = document.getElementById('map-iframe');
        iframe.src = '/api/map';
      }
      if (tabId === 'calibration') {
        loadConfig();
      }
    }

    async function loadTelemetry() {
      try {
        const res = await fetch('/api/stats');
        const data = await res.json();

        const summary = data.gift_summary;
        document.getElementById('total-checks').textContent = summary.total_checks;
        document.getElementById('total-gifts').textContent = summary.collected_count;
        const rate = summary.total_checks > 0 ? Math.round((summary.collected_count / summary.total_checks) * 100) : 0;
        document.getElementById('efficiency').textContent = rate + '%';

        const dBody = document.querySelector('#doggo-table tbody');
        dBody.innerHTML = '';
        const names = Object.keys(summary.by_doggo);
        if (names.length === 0) {
          dBody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: #90a4ae;">No doggos tamed yet.</td></tr>';
        } else {
          names.forEach(name => {
            const row = document.createElement('tr');
            row.innerHTML = `<td><b>${name}</b></td><td>${summary.by_doggo[name].checks}</td><td>${summary.by_doggo[name].collected}</td>`;
            dBody.appendChild(row);
          });
        }

        const rBody = document.querySelector('#runs-table tbody');
        rBody.innerHTML = '';
        if (data.recent_runs.length === 0) {
          rBody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: #90a4ae;">No recent runs.</td></tr>';
        } else {
          data.recent_runs.forEach(run => {
            const row = document.createElement('tr');
            const details = Object.entries(run)
              .filter(([k]) => !['workflow_type', 'saved_at'].includes(k))
              .map(([k, v]) => `${k}: <b>${typeof v === 'object' ? JSON.stringify(v) : v}</b>`)
              .join(' | ');

            row.innerHTML = `<td><b>${run.workflow_type}</b></td><td>${run.saved_at}</td><td>${details}</td>`;
            rBody.appendChild(row);
          });
        }

        loadAuditLogs();
      } catch (err) {
        console.error('Failed loading stats:', err);
      }
    }

    async function loadAuditLogs() {
      try {
        const res = await fetch('/api/audit');
        const items = await res.json();

        const body = document.querySelector('#audit-table tbody');
        body.innerHTML = '';
        if (items.length === 0) {
          body.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #90a4ae;">No audits logged. Ensure Temporal is running.</td></tr>';
        } else {
          items.forEach(item => {
            const row = document.createElement('tr');
            let color = '#cfd8dc';
            if (item.status === 'RUNNING') color = '#00e5ff';
            if (item.status === 'COMPLETED') color = '#00e676';
            if (item.status === 'FAILED' || item.status === 'TERMINATED') color = '#ff1744';

            row.innerHTML = `
              <td><code>${item.id}</code></td>
              <td><b>${item.type}</b></td>
              <td><span style="color: ${color}; font-weight: bold;">${item.status}</span></td>
              <td>${item.start_time}</td>
              <td>${item.close_time}</td>
              <td><span style="color: #ffd600;">${item.principal}</span></td>
            `;
            body.appendChild(row);
          });
        }
      } catch (err) {
        console.error('Failed loading audit logs:', err);
      }
    }

    async function loadGallery() {
      try {
        const res = await fetch('/api/screenshots');
        const items = await res.json();

        const container = document.getElementById('gallery-container');
        container.innerHTML = '';
        if (items.length === 0) {
          container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: #90a4ae; padding: 50px;">No debug screenshots captures yet.</div>';
        } else {
          items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'gallery-item';
            div.innerHTML = `
              <img src="/screenshots/${item.name}" onclick="window.open('/screenshots/${item.name}')">
              <div class="gallery-info">
                <div><b>${item.name}</b></div>
                <div style="color: #80deea; font-size: 10px; margin-top: 4px;">${item.timestamp}</div>
              </div>
            `;
            container.appendChild(div);
          });
        }
      } catch (err) {
        console.error('Failed loading screenshots:', err);
      }
    }

    let currentVersion = 0;
    async function watchSaveFile() {
      try {
        const res = await fetch(`/api/watch?version=${currentVersion}`);
        const data = await res.json();
        if (data.version > currentVersion) {
          currentVersion = data.version;
          loadTelemetry();
          loadGallery();
          loadAuditLogs();
          const iframe = document.getElementById('map-iframe');
          if (iframe && iframe.src) {
            iframe.src = '/api/map';
          }
          showNotification('Save file updated! Auto-reloaded telemetry.');
        }
      } catch (e) {
        // Retry
      }
      setTimeout(watchSaveFile, 1000);
    }

    let zoomScale = 1.0;
    function zoomFlowchart(factor) {
      if (factor === 0) {
        zoomScale = 1.0;
      } else {
        zoomScale = Math.max(0.15, Math.min(3.0, zoomScale + factor));
      }
      const container = document.getElementById('flowchart-container');
      const svg = container.querySelector('svg');
      if (svg) {
        if (!svg.dataset.origWidth) {
          svg.dataset.origWidth = svg.getAttribute('width') || svg.getBoundingClientRect().width;
          svg.dataset.origHeight = svg.getAttribute('height') || svg.getBoundingClientRect().height;
        }
        const w = parseFloat(svg.dataset.origWidth);
        const h = parseFloat(svg.dataset.origHeight);
        svg.setAttribute('width', (w * zoomScale) + 'px');
        svg.setAttribute('height', (h * zoomScale) + 'px');
      }
    }

    let isPanning = false;
    let startX = 0, startY = 0;
    let scrollLeft = 0, scrollTop = 0;

    function initFlowchartPan() {
      const wrapper = document.getElementById('flowchart-wrapper');
      if (!wrapper) return;

      wrapper.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return;
        isPanning = true;
        wrapper.style.cursor = 'grabbing';
        startX = e.pageX - wrapper.offsetLeft;
        startY = e.pageY - wrapper.offsetTop;
        scrollLeft = wrapper.scrollLeft;
        scrollTop = wrapper.scrollTop;
      });

      wrapper.addEventListener('mouseleave', () => {
        isPanning = false;
        wrapper.style.cursor = 'grab';
      });

      wrapper.addEventListener('mouseup', () => {
        isPanning = false;
        wrapper.style.cursor = 'grab';
      });

      wrapper.addEventListener('mousemove', (e) => {
        if (!isPanning) return;
        e.preventDefault();
        const x = e.pageX - wrapper.offsetLeft;
        const y = e.pageY - wrapper.offsetTop;
        const walkX = (x - startX);
        const walkY = (y - startY);
        wrapper.scrollLeft = scrollLeft - walkX;
        wrapper.scrollTop = scrollTop - walkY;
      });
    }

    loadTelemetry();
    loadGallery();
    watchSaveFile();
    initFlowchartPan();
  </script>
</body>
</html>
"""


def start_server(port: int = 8080) -> None:
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    # Start the save watcher thread in background
    watcher_thread = threading.Thread(target=watch_save_files, daemon=True)
    watcher_thread.start()

    server_address = ("", port)
    try:
        httpd = ThreadedHTTPServer(server_address, DashboardHandler)
        print("\n==================================================")
        print("  Starting Satisfactory Bot Dashboard Server...")
        print(f"  Url: http://localhost:{port}")
        print("==================================================")
        print("Press Ctrl+C to stop the dashboard server.")

        # Open browser in a separate thread so it doesn't block the server loop start
        threading.Timer(0.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()

        httpd.serve_forever()
    except Exception as exc:
        print(f"Error starting dashboard server: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    start_server()
