# satisfactory-ai roadmap

This project owns its roadmap: update it in the same commit as the work.
Format and checker: `pdt roadmap check` (personal-devtools `personal_devtools/roadmap.py`).
The fleet-wide view is generated from every project's pushed `ROADMAP.md`
(`pdt roadmap status`, fleet-docs *Fleet Status*); never edit that page by hand.

## Open

| ID | Item | Status | Priority | Done when |
| --- | --- | --- | --- | --- |
| SAT-6 | Repair the validation gate and clean-checkout build: `compose.yaml` instead of `docker-compose.yml`, track `uv.lock`, untrack the compose `.bak` | planned | P1 | On a fresh clone `docker compose build` succeeds and every command in `project-policy.toml` `validation.commands` exits 0, including a non-skipped `uv lock --check` |
| SAT-7 | Fast Gitea CI workflow (waiting on: SAT-6) | planned | P2 | A push runs ruff, mypy, `uv lock --check` and `uv run pytest -m 'not e2e'` on Gitea Actions with SHA-pinned actions, and the latest run on main is green |
| SAT-8 | Register and apply the `e2e` marker to the Playwright dashboard test | planned | P2 | `uv run pytest -m 'not e2e' --collect-only -q` lists no test from `tests/test_playwright_dashboard.py` and the marker is registered in `pyproject.toml` (no unknown-marker warning) |
| SAT-1 | Save-file factory telemetry as OTel gauges plus a Grafana dashboard | planned | P2 | After `sbot plan --track`, ClickHouse has gauge rows for save age, phase, alternates unlocked and sink points, and the Grafana dashboard shows them for the last 7 days |
| SAT-3 | AFK session watchdog: last-gift-age metric and an alert (waiting on: SAT-1) | planned | P2 | Stopping the game worker for longer than 3x the farm interval fires the Grafana alert, and the alert also fires when the metric is absent |
| SAT-5 | `sbot gifts report`: per-doggo gifts/hour, median gap, empty ratio, suggested interval | planned | P3 | `sbot gifts report` on the real `stats/gift_history.db` prints those four figures per doggo with sample size, covered by a unit test on a fixture DB |
| SAT-2 | Read-only MCP server exposing save summary, production plan, gift summary and workflow status | planned | P3 | An MCP client lists exactly 4 read-only tools and `save_summary` returns the same phase as `sbot save`; no tool can start or signal a workflow |
| SAT-4 | `sbot recipes check`: compare `recipe_db.py` with the installed game's `Docs/en-US.json` | planned | P3 | Running it against the local install prints a mismatch report (count of differing and missing recipes, possibly 0) without committing any Docs file |
| SAT-9 | Retention policy for `stats/`, `captures/`, `debug_screenshots/`, `logs/` | planned | P3 | A prune command or timer keeps each directory under a configured size, and a disk-usage gauge for them is visible in Grafana |
| SAT-10 | Container and config hygiene: pin the uv image and base image, drop the `./workflows` bind mount, make the OTLP endpoint config-only, untrack `graphify-out/` (waiting on: SAT-6) | planned | P3 | `grep -rn '172.28.125.187' workers/` and `grep ':latest' Dockerfile` return nothing, `git ls-files graphify-out` is empty, and the built image runs the orchestrator without the workflows mount |

### SAT-6
Verified by reading: `project-policy.toml` exits 1 if `docker-compose.yml` exists (it does); `Dockerfile` copies `uv.lock`, which `.gitignore` excludes and is untracked. Details in [the round-2 doc](docs/research/2026-09-30-features-and-refinement.md).

### SAT-7
No `.gitea/workflows` or `.github` exists. Reuse the fleet marker filter `-m 'not e2e'` in the repo's own CI as well. See [the round-2 doc](docs/research/2026-09-30-features-and-refinement.md).

### SAT-8
`tests/test_playwright_dashboard.py` has no marker or skip and needs a Playwright browser; `pyproject.toml` registers no markers. See [the round-2 doc](docs/research/2026-09-30-features-and-refinement.md).

### SAT-1
Comparable: https://github.com/featheredtoast/satisfactory-monitoring (Prometheus, Grafana, Discord alerts from the FRM mod). This is the mod-free, save-based variant. Cap per-item labels. See [the round-2 doc](docs/research/2026-09-30-features-and-refinement.md).

### SAT-3
Host-worker-down leaves workflows looking healthy (docs/deploy.md), so the check reads gift DB freshness. The alert window must scale with the farm interval and must detect absence. See [the round-2 doc](docs/research/2026-09-30-features-and-refinement.md).

### SAT-5
Internal data only (`utils/gift_db.py` `gift_intervals`, `summary`); no external comparable found. See [the round-2 doc](docs/research/2026-09-30-features-and-refinement.md).

### SAT-2
Comparable: https://github.com/obuter/satisfactory-mcp (10 read-only tools over the FRM mod). Here the tools wrap existing Python functions. See [the round-2 doc](docs/research/2026-09-30-features-and-refinement.md).

### SAT-4
Game Docs JSON: https://satisfactory.wiki.gg/wiki/Community_resources (UTF-16, no explicit licence, so read at runtime, never commit). Report-only first. See [the round-2 doc](docs/research/2026-09-30-features-and-refinement.md).

### SAT-9
`stats/` (gift DB, icon crops, session JSON) and capture directories are gitignored and unbounded. See [the round-2 doc](docs/research/2026-09-30-features-and-refinement.md).

### SAT-10
Also covers dependency currency: `>=` floors in `pyproject.toml` plus an untracked lock give no reproducible scan input. See [the round-2 doc](docs/research/2026-09-30-features-and-refinement.md).

## Done

## Notes

No pre-existing prose. Round 2 research: [docs/research/2026-09-30-features-and-refinement.md](docs/research/2026-09-30-features-and-refinement.md).
