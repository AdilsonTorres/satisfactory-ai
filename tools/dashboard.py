"""
tools/dashboard.py

A lightweight dashboard server for monitoring autonomous satisfactory loops.
Serves a Single Page Application with interactive tabs for:
1. Telemetry stats and SQLite taming metrics.
2. Visual calibration crop gallery.
3. Live power grid and POI visualizer map.
"""

import http.server
import json
import socketserver
import sqlite3
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tools.map_power import generate_power_map  # noqa: E402


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging to stdout to keep CLI clean
        pass

    def do_GET(self):
        # Serve API: Stats & SQLite metrics
        if self.path == "/api/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = self._get_stats_data()
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
        # Dynamically trigger fresh map power grid reconstruction on load
        try:
            result = generate_power_map()
            if not result:
                return "<h3>Error: Power map generation returned no data. Ensure a save file exists.</h3>"

            # Re-read stats/reachable_power_map.html produced by visualizer
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
  </div>

  <script>
    function switchTab(tabId) {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      // Mark selected active
      const clickedTab = Array.from(document.querySelectorAll('.tab')).find(t => t.textContent.includes(tabId === 'telemetry' ? 'Telemetry' : tabId === 'gallery' ? 'Screenshot' : 'Power Grid'));
      if (clickedTab) clickedTab.classList.add('active');

      const content = document.getElementById(tabId);
      if (content) content.classList.add('active');

      if (tabId === 'map-view') {
        const iframe = document.getElementById('map-iframe');
        iframe.src = '/api/map';
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

        // Update doggo table
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

        // Update runs table
        const rBody = document.querySelector('#runs-table tbody');
        rBody.innerHTML = '';
        if (data.recent_runs.length === 0) {
          rBody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: #90a4ae;">No recent runs.</td></tr>';
        } else {
          data.recent_runs.forEach(run => {
            const row = document.createElement('tr');
            // Clean display of extra data fields
            const details = Object.entries(run)
              .filter(([k]) => !['workflow_type', 'saved_at'].includes(k))
              .map(([k, v]) => `${k}: <b>${typeof v === 'object' ? JSON.stringify(v) : v}</b>`)
              .join(' | ');

            row.innerHTML = `<td><b>${run.workflow_type}</b></td><td>${run.saved_at}</td><td>${details}</td>`;
            rBody.appendChild(row);
          });
        }
      } catch (err) {
        console.error('Failed loading stats:', err);
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

    // Auto-refresh stats
    loadTelemetry();
    loadGallery();
    setInterval(loadTelemetry, 5000);
  </script>
</body>
</html>
"""


def start_server(port: int = 8080) -> None:
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    server_address = ("", port)
    try:
        httpd = ThreadedHTTPServer(server_address, DashboardHandler)
        print("\n==================================================")
        print("  Starting Satisfactory Bot Dashboard Server...")
        print(f"  Url: http://localhost:{port}")
        print("==================================================")
        print("Press Ctrl+C to stop the dashboard server.")

        # Open browser in a separate thread so it doesn't block the server loop start
        import threading

        threading.Timer(0.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()

        httpd.serve_forever()
    except Exception as exc:
        print(f"Error starting dashboard server: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    start_server()
