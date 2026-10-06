# satisfactory-ai: fleet research, 2026-10-05

Local research on my-scorpion and pc-home. Scope: existing source/roadmaps, live checkup and primary upstream documentation. Base source: `a7edc4df`; branch: `research/fleet-2026-10-05`. This is not pushed fleet truth and does not certify the older deployed release.

## Current evidence and boundaries

pc-home-only X11/Xwayland AFK bot, no LLM; 3 existing local commits and 6 dirty generated files are unrelated and preserved.

Local anchors: `README.md`, `pyproject.toml`. README/ROADMAP and configuration are the starting points, not a line-by-line proof of all code. Declared Python constraint: ">=3.14". Locked dependencies and Docker pins remain unchanged by this research.

## Consolidation / split / replacement decision

Keep input automation isolated; compare reuse of personal Temporal versus dedicated ports only after safety tests.

Retain existing working components unless a measured trial beats them. New dependencies must justify operational cost, compatibility, backup/rollback and quality. Existing owner gates and time-gated evidence remain open; no paid benchmark, GPU wake-up, game input or live user messaging is authorized by this document.

## Proposed work

### SAT-100: Focus-loss watchdog, input release and deterministic replay tests

Priority/status: P2 / planned. Rationale: No live game input executed during research. Human-visible stop control is a safety prerequisite for any new behavior.

Acceptance: Synthetic focus loss/pause/crash always releases held keys/buttons within 1s; game input is never sent to an unrelated foreground window in tests.

Research basis: [pytest flaky-test guidance](https://docs.pytest.org/en/stable/explanation/flaky.html) (consulted 2026-10-05). The proposed fleet benefit and thresholds are an engineering hypothesis, not an upstream performance guarantee. Implement in an isolated branch/staging environment, compare against current behavior, and keep a reversible rollback.

### SAT-101: Temporal placement and visual-loop profiling feasibility

Priority/status: P3 / planned. Rationale: Don't point bot at fleet namespace or restart services merely to simplify deployment; optional existing shared cluster requires explicit ownership decision.

Acceptance: Record current localhost7233 ownership/port conflict and dedicated-versus-shared namespace tradeoff; copied frames report detector/OCR p95 and CPU without game IO.

Research basis: [Python workflow sandbox](https://docs.temporal.io/develop/python/python-sdk-sandbox) (consulted 2026-10-05). The proposed fleet benefit and thresholds are an engineering hypothesis, not an upstream performance guarantee. Implement in an isolated branch/staging environment, compare against current behavior, and keep a reversible rollback.

## Validation status

Research and roadmap changes do not prove implementation. No proposal benchmark, full application E2E, live restore, GPU-quality panel or upgrade was run here. Concrete validation of the temporary observability disablement and fleet roadmap gates is recorded in fleet-docs `docs/05-roadmaps-and-history/fleet-research-2026-10-05.md`. Re-check upstream releases at implementation time; a release existing is not evidence it is safe for every consumer.
