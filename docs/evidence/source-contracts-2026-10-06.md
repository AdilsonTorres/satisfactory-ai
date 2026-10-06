# Satisfactory source contracts and stack research — 2026-10-06

Only the isolated research clone is edited. The real pc-home main checkout has
six dirty user entries, retained unread/unmodified. No game input, screenshot,
GPU activation, live Temporal trigger, deployment or push occurred.

## Every prior open row against critical source

| Row | Verified source | Refined decision |
| --- | --- | --- |
| SAT-100 | `utils/input.py`, both recapture callers, worker F9 stop and activity/workflow cancellation boundaries | Fix recapture locally but retain whole-input watchdog, offline interruption and owner compositor/crash qualification; observed readback is not an atomic lease |
| SAT-101 | Compose has only orchestrator; shared address and `satisfactory-ai` namespace already configured; workflow/game activity polls deliberately split | Withdraw required localhost migration/port-conflict assumption; preserve namespace/isolation and benchmark only controlled copied frames without game IO |

The reviewed paths include configuration defaults, orchestrator/host worker
ownership, CLI calibration/exploration/status, input focus/readback/release,
menu/camera-probe callers, replay/cancellation timeout context, Docker build and
project conventions. This is not every detector, planner, dashboard or factory
algorithm reviewed; solid/fluid planning rules remain unchanged.

## Reproductions and narrow fixes

Three old-source device-free controls failed: failed activation still accessed
the mouse and clicked, focus readback was absent before recapture, and an
interrupted held click skipped release. `FocusNotReadyError` now stops callers
even if they ignore the former Boolean return. Focus is checked before cursor
movement and each recapture click, with release in `finally`. Five controls pass,
including paired normal clicks and loss before the second click. Time-of-check
versus input remains racy, and no physical <=1s/crash guarantee is claimed.

Six old-source CLI scope controls failed. Calibration/exploration used localhost
and default namespace; status used the configured address but omitted namespace
and environment overrides. These three paths now resolve address/namespace like
workers, with project namespace fallback; triggers honor configured task queue.
Six fake-client controls pass for configuration and environment overrides. No
workflow was started. Other script/dashboard Client.connect sites still need
SAT-103; these fixes are not proof of fleet-wide client consistency.

An existing input test now mocks active-window readback instead of querying a
real desktop. All new controls use fake evdev/pynput/Temporal modules and forbid
real devices, keeping the checks independent of a display or dependency sync.
The existing fail-safe key test now reports missing pynput as skipped rather
than returning a false pass; the worker-import/backend case remains separately
unverified by the 11 dependency-free controls.

## Features, consolidation, replacements and versions

SAT-102: F9 currently awaits schedule listing/pausing and running-workflow listing
and signals before `os._exit`. There is no local-first bounded network policy;
selection is all running workflows in the connected namespace, not an owned
type/ID allowlist. A namespace mistake can target unintended workflows, though
unknown signals are not proof that those workflows terminate. `_exit` skips
Python cleanup handlers; the OS closes descriptors, so orphan devices/permanent
held keys are not proven. Keep emergency release local and qualify cancellation
of threaded activities rather than assume a Temporal signal preempts input.

Keep the existing Temporal cluster and project namespace; do not merge gameplay
activities into homelab maintenance workers or add a second private cluster.
Keep the input adapter separate from deterministic planner/vision replay. First
measure existing evdev/KWin/OpenCV/Tesseract paths; a new privileged input daemon,
GPU detector, agent/LLM loop or new orchestration tool adds unproven operational
cost and is not required to fix the observed defects.

Current primary PyPI metadata checked 2026-10-06: temporalio 1.34.0, evdev 2.0.0,
opencv-python 5.0.0.93, numpy 2.5.3, pynput 1.8.2 and mss 10.2.0. These are available
versions, not installed runtime versions. Existing broad minimums can resolve
major changes; no dependency or GPU/game runtime was upgraded here. A tracked
lock is absent and `.gitignore` excludes `uv.lock`, while Docker requires
`COPY pyproject.toml uv.lock` and frozen sync. SAT-104 requires isolated version
qualification, source-owned lock and a clean build; no successful image build is
claimed. Consider headless OpenCV only for replay/CLI after GUI dependency usage
is enumerated and output equivalence measured, not as a blanket replacement.

## Independent delegated review

AGY `gemini-3.8-flash-high` static-snippet review returned successfully (conversation
`7e10964a-cfc9-4804-ac11-538548fa244b`, one reported turn, 24.4 s; 16,282 reported
tokens). It identified focus, shutdown cleanup and namespace selection risks;
the three focus controls and source inspection independently support the narrow
findings above. Its stronger orphan-device/guaranteed-release wording was not
adopted. Prompt forbade tools/writes/live access; no tool calls were reported.
This is not provider wire-level or token-cost-saving evidence.

## Primary sources and validation limits

- [Temporal Client API](https://python.temporal.io/temporalio.client.Client.html#connect): address and namespace are independent client scope parameters.
- [Temporal Python cancellation](https://github.com/temporalio/sdk-python#cancellation): activity heartbeat/cancellation semantics; no blanket hard-preemption guarantee.
- [Python process exit](https://docs.python.org/3/library/os.html#os._exit): cleanup handlers are bypassed, not evidence of physical input persistence.
- [Linux uinput](https://docs.kernel.org/input/uinput.html), [evdev injection](https://python-evdev.readthedocs.io/en/latest/tutorial.html#injecting-input): existing adapter and controlled device qualification.
- [temporalio](https://pypi.org/project/temporalio/), [evdev](https://pypi.org/project/evdev/), [OpenCV wheels](https://pypi.org/project/opencv-python/): current upstream candidates; not automatic compatibility proof.

my-scorpion: 11 new device-free controls pass and changed-scope Ruff lint passes.
Pre-commit and pc-home verification are recorded in the fleet ledger when done.
The full default suite/mypy requires project dependencies and may contain
display/game assumptions; it has not been certified by these isolated controls.
No deployed/UI/physical input/replay dataset benchmark or complete multi-round
fleet revision is claimed.
