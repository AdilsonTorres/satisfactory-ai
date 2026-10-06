# satisfactory-ai roadmap

Owner-requested local research; this project owns its roadmap. No publishing or automatic reactivation.

## Open

Research rationale and adoption gates: [baseline](docs/evidence/fleet-research-2026-10-05.md) and [source verification](docs/evidence/source-contracts-2026-10-06.md). Local changes are not deployed; private pc-home user edits remain untouched.

| ID | Item | Status | Priority | Done when |
| --- | --- | --- | --- | --- |
| SAT-100 | Whole-input focus-loss watchdog and release contract; recapture guard is only partial | planned | P2 | Offline stop/pause/interruption controls cover every held key/button; owner-authorized compositor/process-crash tests qualify a <=1s release bound and foreground ownership; readback alone is not an atomic lease |
| SAT-101 | Existing shared-cluster isolation and visual-loop profiling | planned | P3 | Preserve project namespace and worker/activity split; controlled copied frames measure detector/OCR p95, CPU and correctness with provenance; no game/GPU IO during offline profiling |
| SAT-102 | Local-first bounded emergency stop with owned Temporal targets | planned | P2 | Local input release does not wait on network; inaccessible server and concurrent stop tests pass; schedule/workflow allowlist cannot signal unrelated namespace workloads; process exit/FD cleanup and physical release qualify separately |
| SAT-103 | Unified Temporal scope across scripts, dashboard and CLI | testing | P2 | Remaining Client.connect sites consistently honor configured namespace/address and environment; task queues are explicit; synthetic wrong-scope tests deny unintended workloads; no live trigger or shared-namespace migration |
| SAT-104 | Reproducible frozen build and device-free CI qualification | planned | P2 | Docker-required ignored uv.lock becomes source-owned after isolated dependency qualification; exact SDK/CV/input versions have replay/numeric/device-free controls; clean checkout builds without private frames or live IO |

## Done

- 2026-10-06 — SAT-105: recapture fails before device access on unverified focus, rechecks clicks and pairs release on exceptions; five device-free controls, not the full watchdog
- 2026-10-06 — SAT-106: calibration/exploration/status CLI use configured address, namespace and env overrides; trigger queues configured; six offline scope controls, no live send
