# Features and roadmap refinement (round 2, 2026-09-30)

## Context

satisfactory-ai is a local Satisfactory AFK bot (screen capture, OpenCV, uinput) orchestrated by Temporal, plus the `sbot` CLI (save parser, gameplay plan, production planners, dashboard). The orchestrator worker runs in Docker against the shared Temporal cluster; the game worker runs on the desktop session. Data already collected: `stats/gift_history.db` (SQLite), `stats/save_history.json` (`sbot plan --track`), session stats JSON, OTLP logs to the fleet collector.
Round 1 research doc (`docs/research/2026-09-30-improvement-research.md`) and `ROADMAP.md` did NOT exist in this worktree, so round-1 rows could not be read or refined. This round therefore created `ROADMAP.md` from scratch (SAT-1 onward) and covers the whole improvement space. Nothing here was executed; repo claims are from reading files only.

## New features

### SAT-1 Factory telemetry from the save file to OTel/Grafana
- User story: see power, production, sink and unlock progress over time in the existing Grafana, and get alerts, without opening the game. Today `sbot plan --track` appends to a local JSON and only prints deltas.
- Evidence: featheredtoast/satisfactory-monitoring turns game data into Prometheus metrics, Grafana dashboards and Discord alerts (power circuit failure, overconsumption, fuse trips), https://github.com/featheredtoast/satisfactory-monitoring . That stack needs the Ficsit Remote Monitoring game mod (live data); this project already parses `.sav` files, so the save-based variant needs no mod and no game-install change. Save data is only as fresh as the last autosave.
- Smallest version: `sbot plan --track` also emits a handful of OTel gauges (save age, phase, alternates unlocked, sink points, item counts already parsed) via the OTLP setup already in `workers/worker.py`; one Grafana dashboard JSON with 4 panels. No alerts yet.
- Effort: M. Risk: parser drift after game updates (save format is versioned; `save_parser.py` is hand-written); metric cardinality if per-item labels are unbounded (cap the item list).
- Roadmap ID: SAT-1. Waiting on: none (SAT-9 retention is independent).

### SAT-2 Read-only MCP server for agents
- User story: ask Claude/Codex "what alternates am I missing, what is my Modular Frame plan at 10/min, how did the doggo farm do this week" against live project data instead of pasting CLI output.
- Evidence: obuter/satisfactory-mcp exposes 10 read-only tools (health_check, factory_summary, power_status, production_stats, find_bottlenecks, ...) to MCP clients (Claude Desktop, Claude Code), https://github.com/obuter/satisfactory-mcp . It reads the FRM mod; here the same shape would read the save parser, `gift_db.summary()`, recipe planner and Temporal status, all of which already exist as Python functions. The fleet already runs FastMCP servers (`pdt mcp`).
- Smallest version: stdio FastMCP server, 4 read-only tools: `save_summary`, `plan_production(item, rate)`, `gift_summary`, `workflow_status`. No tool starts or signals workflows.
- Effort: S-M. Risk: adds a dependency (fastmcp) and a second entry point; keep it read-only so an agent cannot drive the game.
- Roadmap ID: SAT-2. Waiting on: none.

### SAT-3 AFK session watchdog with alert
- User story: get told when a multi-hour farm has silently stopped producing (game worker down, game crashed or paused, doggo detection failing) instead of finding out next morning.
- Evidence: the monitoring stacks above route alerts through Alertmanager to Discord (same README as SAT-1). Locally: docs/deploy.md states that with the host worker down, activities just wait in the queue, so a running workflow looks healthy in Temporal while nothing happens.
- Smallest version: a check that reads the newest `gift_history.db` row timestamp per active doggo and the running workflow list, exports `satisfactory_last_check_age_seconds`, and one Grafana alert rule whose window is a multiple of the configured `--interval` (window must match producer cadence). Alert must also fire when the metric is absent.
- Effort: S-M. Risk: false alarms when the player is intentionally playing; needs a pause flag or schedule awareness (`sbot schedules`).
- Roadmap ID: SAT-3. Waiting on: SAT-1 (shares the OTel metric path).

### SAT-4 Recipe data generated from the game's own Docs file
- User story: planners stay correct after a game patch without hand-editing the 1000-line `RECIPES` dict in `utils/recipe_db.py`.
- Evidence: the game ships localized JSON data dumps (items, recipes, buildings, schematics) in its Docs folder, UTF-16, no explicit licence, https://satisfactory.wiki.gg/wiki/Community_resources ; community parsers exist (dmryabov/satisfactory-docs-exporter, lunafoxfire/satisfactory-docs-parser, Maurdekye/satisfactory-recipe-parser; URLs from search results only, not fetched, unverified).
- Smallest version: `sbot recipes check` reads `Docs/en-US.json` from the local install at runtime (do NOT commit it: no licence) and reports recipes in `recipe_db.py` whose inputs/outputs/machine differ or are missing. Report only; no generation yet.
- Effort: M. Risk: Docs schema quirks (UTF-16, class-name strings); the install path on Linux/Proton must be configured, unverified.
- Roadmap ID: SAT-4. Waiting on: none.

### SAT-5 Gift-farm yield report and interval advice
- User story: know items per hour per doggo and whether the configured interval wastes checks or misses gifts. `gift_db.gift_intervals()` and `summary()` already exist but nothing turns them into a decision.
- Evidence: no comparable external tool found; this rests on data the project already records (timestamp, item, slot diff per check). Marked internal-only.
- Smallest version: `sbot gifts report` printing per-doggo gifts/hour, median gap between gifts, empty-check ratio and a suggested `--interval` (e.g. half the median gap). Read-only.
- Effort: S. Risk: low; small sample sizes give noisy advice (print n).
- Roadmap ID: SAT-5. Waiting on: none.

## Further improvements

Covers the whole space (no round-1 rows existed).

- SAT-6 (P1): `project-policy.toml` validation exits 1 when `docker-compose.yml` exists, and the repo has only `docker-compose.yml` (plus a tracked `docker-compose.yml.bak-20260729`), so the fleet gate fails today. Separately `Dockerfile` does `COPY pyproject.toml uv.lock ./` while `.gitignore` lists `uv.lock` and it is not tracked, so a clean checkout cannot build the image and `uv lock --check` in the gate is skipped. Fix: rename to `compose.yaml`, track `uv.lock`, untrack the `.bak`.
- SAT-7 (P2): no CI at all (`.gitea/workflows` and `.github` absent). Add a fast workflow: ruff, mypy, `pytest -m 'not e2e'`, `uv lock --check`, SHA-pinned actions. Waiting on SAT-6 (needs `uv.lock`).
- SAT-8 (P2): `tests/test_playwright_dashboard.py` has no marker or skip, so it runs in the `-m 'not e2e'` gate and needs a Playwright browser. `e2e` is not registered in `pyproject.toml`. Register and apply the marker; also note only 19 test files for 3 workers and about 12 workflows (no coverage number measured).
- SAT-9 (P3): unbounded growth in `stats/` (gift DB, icon crops, per-session JSON), `captures/`, `debug_screenshots/`, `logs/`; no prune or size metric. Add a retention policy plus a disk-size gauge (tie to SAT-1).
- SAT-10 (P3): container and config hygiene: `ghcr.io/astral-sh/uv:latest` unpinned in `Dockerfile`; `debian:bookworm-slim` unpinned by digest; compose bind-mounts `./workflows` over the image copy (image and running code can diverge); `workers/worker.py` defaults the OTLP endpoint to the hardcoded `172.28.125.187:4317`; 102 `graphify-out/` files tracked. Dependency CVE currency: pyproject uses `>=` floors only and no lock is tracked, so there is no reproducible scan input (depends on SAT-6).

## Roadmap refinement notes

No pre-existing roadmap rows: `ROADMAP.md` was created this round. Notes on other pre-existing artifacts:
- `docs/deploy.md` and README still refer to `docker compose` for a private Temporal stack in places (README "Setup 3" lists Temporal Server, Postgres and UI on ports 7233/8233), while `docker-compose.yml` says the private cluster was retired on 2026-07-29 in favour of the shared cluster. Stale, needs an owner decision on what README should say.
- `GEMINI.md` diagram still shows the local Temporal server 1.31.2 and Postgres 18 (retired), and links to `/home/adilson/Projects/github/...`.
- README references `capture_template.py`, `debug_run.py`, `passive_capture.py`, `label_captures.py` at repo root; these now live in `tools/` (only `sbot` subcommands are current). Unverified whether root wrappers exist (root has trigger_*.py scripts only).

## Considered and rejected

- Dedicated-server HTTPS API for save management (https://satisfactory.wiki.gg/wiki/Dedicated_servers/HTTPS_API): the bot drives a desktop game client with uinput; the API applies only to a dedicated server, which would be new hosting and a different play setup.
- Adopting the Ficsit Remote Monitoring mod for live data: modifies the game install, Proton compatibility unverified; the save-file route (SAT-1) covers most value without it. Revisit if save freshness is not enough.
- Local vision-LLM "am I stuck" detector on screenshots: the single GPU is shared with the running game (and the fleet mode switcher), so a resident VLM competes for VRAM; CPU tier is too slow for this. Existing OpenCV templates plus SAT-3 are cheaper.
- Cloud/paid notification or observability services: rejected by rule; use the existing Grafana alerting.
- Web UI to control workflows: `sbot dashboard` already exists (1745 lines); more UI adds maintenance without a new capability.

## Sources

Fetched 2026-09-30:
- https://github.com/obuter/satisfactory-mcp
- https://github.com/featheredtoast/satisfactory-monitoring
- https://satisfactory.wiki.gg/wiki/Dedicated_servers/HTTPS_API
- https://satisfactory.wiki.gg/wiki/Community_resources

Seen in search results only (not fetched, unverified beyond the snippet): https://github.com/AP-Hunt/FicsitRemoteMonitoringCompanion , https://github.com/dmryabov/satisfactory-docs-exporter , https://github.com/lunafoxfire/satisfactory-docs-parser , https://github.com/Maurdekye/satisfactory-recipe-parser , https://github.com/etothepii4/satisfactory-file-parser
