# Satisfactory AFK Bot + Temporal

Local bot for AFK farming in Satisfactory. No cloud, no LLM in the loop.
Orchestration via Temporal for automatic retries, detailed execution history, and visual debugging.

> **OS requirement:** Linux (X11 / Xwayland).

## Stack

| Component | Lib / Tool | Why |
|---|---|---|
| Screen capture | `mss` | ~1ms per frame |
| Visual detection | `opencv-python` | Template matching, zero training |
| 3D Inputs | `pynput` + `evdev` (uinput) | Keyboard/click input via pynput (X11/Xwayland); a virtual `uinput` mouse for relative camera movement, since Proton/Wine ignores synthetic X11/XTest motion |
| Window focus | `xdotool` | Finds and activates the game window automatically |
| OCR (inventory) | `pytesseract` | Visually reads item quantities in the inventory |
| Orchestration | `temporalio` | Structured retries, flow control (pause/resume/stop), and persistence |
| Packages | `uv` | Fast Python dependency management |
| Temporal services | Docker Compose | PostgreSQL + Temporal Server + Temporal Web UI |

---

## Guides & Documentation

For planning structures and layout automation, refer to the [Satisfactory Game Design & Factory Layout Guides](docs/game_design_guides.md).

---

## Setup

### 1. Prerequisites (Linux)

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Docker](https://docs.docker.com/engine/install/) (with Compose V2)
- Python 3.14+
- `xdotool` on PATH
- `tesseract-ocr` on PATH
- `imagemagick` on PATH (screenshot fallback used when `mss` fails, e.g. on some Xwayland compositors)
- `/dev/uinput` with a `uaccess` ACL for your user (see "Mouse-look" below) — already the case on most distros that ship udev rules for KDE Connect, Steam Input, or antimicrox.

On Ubuntu/Debian, you can install the system dependencies with:
```bash
sudo apt update
sudo apt install xdotool tesseract-ocr imagemagick
```

### 2. Install Python dependencies
Use `uv` to sync and create the virtual environment:
```bash
uv sync
```

### 3. Bring up the Temporal services
Start the Temporal Server and PostgreSQL containers in the background:
```bash
docker compose up -d
docker compose ps   # confirm all 3 services are healthy/running
```

| Service | Port | Description |
|---|---|---|
| Temporal Server | 7233 | gRPC port the worker and client connect to |
| Temporal UI | 8233 | Local web dashboard for debugging workflows (http://localhost:8233) |
| PostgreSQL | (internal) | Stores workflow state and execution history |

### 4. Create the templates
The bot uses template images to make decisions on the game screen. Capture them with:
```bash
# With Satisfactory open and focused:
uv run python capture_template.py
```

**Before starting the worker, verify the image matches:**
```bash
uv run python debug_run.py --scan
```
This takes a screenshot of the current screen and saves an annotated version to `debug_screenshots/` showing which templates were located and with what confidence.

### 5. Run the workers
Two workers split the work (see `docs/deploy.md`):

* **Orchestrator** (Docker, always on): runs all workflows + persistence
  activities. Started automatically by `docker compose up -d` (service
  `worker`).
* **Game worker** (host): runs the activities that drive the game — screen
  capture, uinput, KWin focus — so it must run in your desktop session:

```bash
uv run python workers/worker.py
```

If the game worker is down, workflows keep running in Docker and game
activities wait in the queue until it's back.

## CLI Command Utility (`sbot`)

The project includes a command-line utility named `sbot` to assist in planning gameplay, analyzing save files, and managing automation tasks.

### 1. Installation
To make the `sbot` command globally accessible in your terminal without needing to manually activate the virtual environment, install the project as an editable tool using `uv`:
```bash
uv tool install --editable .
```
This links the executable command `sbot` directly to your user binary path (e.g., `~/.local/bin`), which should be on your shell's `PATH`.

### 2. Usage

#### Gameplay Plan (`sbot plan`)
Analyze your latest save file, review missing S-tier/A-tier alternate recipes, check resource sink coupons, review factory snapshot stats, and display self-updating guide tips:
```bash
# Display the current gameplay plan
sbot plan

# Display the plan and record progress to stats/save_history.json to track deltas over time
sbot plan --track
```

#### Save File Diagnostics (`sbot save`)
Show full diagnostics for a specific save file:
```bash
# Print general save info (location, phase, stats)
sbot save

# Print save info along with tier-list alternate recipe recommendations
sbot save --advisor
```

#### Factory Production Planning (`sbot plan-production`)
Generate an optimized production layout plan for a specific item at a target rate:
```bash
# Plan factory layout to produce 10 Modular Frames per minute
sbot plan-production --item "Modular Frame" --rate 10
```

#### Late-Game Specialized Planning (`sbot plan-late-game`)
Plan late-game production lines (Phase 5 parts) with power shards, Somersloops, fuel generator calculations, and build phasing tier guides:
```bash
# Plan 10 Ballistic Warp Drives per minute with 0.75 recipe multiplier and specific Somersloop amplifications
sbot plan-late-game --item BWD --rate 10 --recipe-multiplier 0.75 --sloops SO DMC
```

#### Layout Visualizer Flowcharts (`--draw`, `--draw-html`)
Both `plan-production` and `plan-late-game` support:
*   `--draw` to generate a copy-pasteable Mermaid flowchart text representing the plan:
    ```bash
    sbot plan-production --item "Modular Frame" --rate 10 --draw
    ```
*   `--draw-html` to generate and open an interactive, rich dark-mode flowchart directly in your web browser:
    ```bash
    sbot plan-production --item "Modular Frame" --rate 10 --draw-html
    ```

#### Workflow Status & Telemetry (`sbot status`)
Inspect currently executing Temporal workflows and their live telemetry:
```bash
sbot status
```

#### Schedule Management (`sbot schedules`)
Manage Temporal gift-farming start/stop schedules:
```bash
# List all schedules
sbot schedules list

# Create a new schedule window
sbot schedules create --name daily --start 08:00 --stop 23:00

# Pause or resume schedules
sbot schedules pause --name daily
sbot schedules unpause --name daily
```

#### Power Grid Map Visualizer (`sbot map`)
Extract your built power network and analyze Lizard Doggo and threat spatial POIs:
```bash
# Print spatial statistics and route chains
sbot map

# Open a beautiful, interactive dark-mode SVG map in your browser
sbot map --draw-html
```

#### Gameplay Dashboard Server (`sbot dashboard`)
Spin up a local web server to monitor live telemetry, taming rates, screenshots, and visual map tabs:
```bash
sbot dashboard --port 8080
```

### 3. Trigger workflows

```bash
# Lizard Doggo gift farm — roster comes from config.toml [[taming.doggos]]
uv run python trigger_gift_farm.py --interval 60

# or via the Temporal CLI:
temporal workflow start \
  --workflow-type GiftFarmWorkflow \
  --task-queue satisfactory-bot \
  --input '[{"name": "doggo-1", "turn_dx": -400}, {"name": "doggo-2", "turn_dx": 400}]'

# Static combat patrol
temporal workflow start \
  --workflow-type CombatPatrolWorkflow \
  --task-queue satisfactory-bot \
  --input '{"max_kills": 30, "screenshot_every_kills": 5}'

# Full AFK session (alternates gift farm and combat)
temporal workflow start \
  --workflow-type AfkSessionWorkflow \
  --task-queue satisfactory-bot \
  --input '{"gift_cycles": 10, "combat_kills_per_rotation": 5, "total_rotations": 20, "screenshot_every_rotations": 1}'

# Manual harvest of a resource node (player already positioned in range)
temporal workflow start \
  --workflow-type ResourceHarvestWorkflow \
  --task-queue satisfactory-bot \
  --input '{"swings_per_cycle": 20, "cycles": 0, "screenshot_every_cycles": 10}'

# Wild Lizard Doggo taming (best-effort, review screenshots)
temporal workflow start \
  --workflow-type TameDoggoWorkflow \
  --task-queue satisfactory-bot \
  --input '{"max_attempts": 5, "seconds_between_attempts": 15}'

# Combat expedition: travel to a location, kill, resupply ammo if needed,
# return, and store the loot in a storage container
temporal workflow start \
  --workflow-type CombatExpeditionWorkflow \
  --task-queue satisfactory-bot \
  --input '{"location": "example_kill_zone", "max_kills": 10, "min_ammo_to_depart": 20, "ammo_per_craft": 50}'

# Unsupervised exploration around the base: walks the route in config.toml
# [[exploration.route]], screenshotting and checking health/death after
# every leg, then automatically retraces the same legs (mirrored) to head
# back. Legs can hold "space" together with movement keys to drive Hover
# Pack ascend/glide (harmless hop if not equipped). Blind and best-effort —
# see "Known limitations" below before running unsupervised for long.
temporal workflow start \
  --workflow-type ExplorationWorkflow \
  --task-queue satisfactory-bot \
  --input '{}'
```

### Calibrating CombatExpeditionWorkflow

This workflow needs more manual calibration than the others because it
generalizes navigation to **arbitrary locations**, not just the fixed Workshop:

1. **Locations** (`config.toml [locations.<name>]`): duplicate the
   `example_kill_zone` block for each combat zone you want, with the real
   key/duration sequence to get there from the base. Also adjust `base`
   with the path back. `arrival_template` is optional — without it,
   navigation is "blind," like the original `navigate_to_equipment_workshop`.
2. **Ammo** (`config.toml [combat.ammo_region]`): the screen region where
   the ammo counter appears in the weapon's HUD, for OCR to read. Take a
   screenshot (`debug_run.py --screenshot`) and measure x,y,w,h in pixels.
   Without calibration, `check_ammo_count` returns -1 and the workflow
   ignores ammo gating (doesn't block, but also doesn't auto-resupply).
3. **Storage** (`templates/storage_prompt.png`, `templates/storage_open.png`):
   capture with `capture_template.py` while looking at a storage container,
   and with the container open.
4. **Inventory grid** (`config.toml [inventory_grid]`): coordinates of the
   first slot and spacing between slots, used by the shift-click that
   deposits loot. This step is best-effort — `open_storage_and_deposit_loot`
   doesn't verify the transfer worked, only that the storage opened.

---

## Runtime control (Signals & Queries)

While workflows are running, you can interact with them without restarting the process:

```bash
# Pause (waits for the current activity to finish, then pauses)
temporal workflow signal --workflow-id <id> --name pause

# Resume execution
temporal workflow signal --workflow-id <id> --name resume

# Stop gracefully (waits for the in-progress activity to finish)
temporal workflow signal --workflow-id <id> --name stop

# Query the current session's stats in real time
temporal workflow query --workflow-id <id> --query-type get_stats
```

---

## Playing manually? Capture data to improve the bot

While you're playing normally (not AFK), you can run a script in parallel
that **only observes the screen and never sends input** — safe to leave
open in a terminal while you play with keyboard/mouse:

```bash
# Takes a screenshot every 4s (default) into captures/, discarding frames
# nearly identical to the last one saved. Ctrl+C to stop.
uv run python passive_capture.py

# More frequent, with a screenshot limit
uv run python passive_capture.py --interval 2 --max-shots 300
```

After the session, review the screenshots and crop new templates or
better variants of existing ones (ex: the same enemy in different poses,
the wild Doggo, the Doggo's loot window):

```bash
uv run python label_captures.py
```

For each image you type the template name to crop (overwrites or creates
`templates/<name>.png`), `d` to discard the image, or Enter to skip.
Reviewed images go to `captures/_reviewed/`.

To validate whether the current templates/thresholds work well against
real gameplay screenshots (instead of just the current screen):

```bash
uv run python debug_run.py --scan-dir captures
```

This reports each template's detection rate across the batch — useful
for noticing misaligned thresholds or templates that need recapturing
before the next AFK session.

---

## Debugging and visualization

### Standalone debug script (no Temporal)
```bash
# Looks for and annotates every template on the current screen
uv run python debug_run.py --scan

# Looks for a specific template
uv run python debug_run.py --find gift_prompt

# Tests search sensitivity with a custom threshold
uv run python debug_run.py --find enemy_spitter --threshold 0.65

# Just takes a screenshot of the primary monitor
uv run python debug_run.py --screenshot
```
All annotated and captured images are saved with a timestamp in `debug_screenshots/`.

### Automatic screenshots on errors/events
Workflows automatically generate captures in relevant situations:
- Failures/exceptions in activities: `error_{activity_name}_TIMESTAMP.png`
- Full inventory: `inv_full_cycle_N_TIMESTAMP.png`
- Character death: `player_death_TIMESTAMP.png`
- Missing respawn button: `respawn_not_found_TIMESTAMP.png`

### Temporal UI dashboard
Open **http://localhost:8233** in your browser to:
- View a detailed timeline of activities.
- Inspect the input and output parameters of each step.
- Investigate detailed error logs and retry attempts of failed activities.

---

## Calibration and Tuning

### 1. Mouse Sensitivity Factor
In `utils/input.py`, the `aim_at_screen_position` method uses the
`aim_sensitivity_factor` property defined in `config.toml`. Adjust it if
aiming overshoots or undershoots the target.

### 2. Visual Comparison Thresholds
Detection precision thresholds are configured in the `[vision.thresholds]`
section of `config.toml`:
- Static menu elements: `0.85–0.90` (high precision).
- Interaction prompts and buttons: `0.80–0.85`.
- Moving enemies: `0.65–0.70` (to compensate for fast movement and silhouette variation).

### 3. Key-Based Navigation Tuning
Since the bot uses fixed-duration key presses for movement (ex: walking
forward for 1.2s), adjust the key durations in seconds in the
`[navigation]` section of `config.toml` until they line up perfectly with
your base's layout.

---

## Known limitations
- **Health is now read from the bar, not the heart icon (fixed 2026-06-25):** the old `health_low_indicator` template matched at conf 0.95-0.96 on *every* check, including at full health, because it keyed off the heart icon's shape — present in the HUD at any health (`TM_CCOEFF_NORMED` is shape-dominant). So `engage_enemy`'s flee branch and `ExplorationWorkflow`'s health-abort fired on the first check, every time. **Replaced** with `Vision.assess()`, which reads the actual health bar: 10 fixed segment boxes to the right of the heart (calibrated live at 2560x1440), counts the lit ones, and reports `health_frac` (1.0 = 10/10). It also returns a `damage_red` vignette metric (corner red bias, baseline ~0.06, spikes while taking damage) and a best-effort Hover Pack `gauge_frac`. Validated live: full health reads 10/10, no false aborts.
- **Slow screen capture was the real movement hazard (fixed 2026-06-25):** on this KDE/Wayland box the game is a GL/Xwayland surface that `mss` and `ffmpeg x11grab` read back as solid black, so capture fell through to `import -window <gameWin>` — a full 2560x1440 GL readback at **~7.5s per frame**. `explore_leg` grabbed a full frame every chunk, so the character stood frozen ~7.5s each check — itself a likely cause of the death below (Hover Pack draining while standing still). **Fixed**: passing `-crop` to `import` reads back only the requested region (~0.2s for the HUD), and `explore_leg` now uses `Vision.assess()` (two small region grabs, ~0.6s total) while *holding the movement keys down the whole leg* (`inp.keys_down`/`keys_up`) — so the character stays in constant motion (the "safe way is constant moving" model) and only pauses ~0.6s per check instead of ~7.5s.
- **Hover-gauge-vs-health death analysis is instrumented, gauge region pending live calibration:** the death mechanism is understood (Hover Pack charge drains as you move out of an electric pole's range → empties → you fall → fall damage → death; health stays full until the fall). `explore_leg` now logs dense per-chunk `samples` (`health_frac`, `gauge_frac`, `damage_red`, every ~1.6s while moving) and rolls `min_health_frac` into stats, so the *next* flight death is fully reconstructable frame-by-frame — unlike the 2026-06-25 death, which had no usable checkpoints. The charge-ring only renders while flying, so `exploration.gauge_subregion` still needs to be read off one live-flight HUD crop before `gauge_frac` reports real fill (until then it logs `null`).
- **Display resolution was miscalibrated:** `config.toml [display]` had `1920x1080` hardcoded, but `debug_run.py --screenshot` on 2026-06-25 confirmed the actual capture resolution is `2560x1440` (matches `mss`'s native monitor capture, and matches other already-correct absolute-pixel calibrations like `taming.drop_point_x/y` = 1280/720, exactly half of 2560/1440). Fixed in `config.toml`. This previously skewed every `screen_width/height`-derived camera center calculation (combat aiming, `_face_doggo_and_recheck`) — recheck `[combat.aim_sensitivity_factor]` if aim still seems off now that centering is correct.
- **Exploration is blind and unsupervised — keep it conservative:** `ExplorationWorkflow` has no real-time hazard awareness (cliffs, water, enemies, fire). It mirrors the existing `navigate_back_to_base` idiom (retrace the same keys/turns in reverse) rather than visual SLAM/pathfinding, so the further/longer a route goes, the more position drift accumulates on return. Keep `[[exploration.route]]` legs short and `max_total_duration_seconds` small, and only extend it incrementally while reviewing `debug_screenshots/explore_leg_*_*` after each run.
- **Death is now actually detectable, and respawn is fixed:** a live flight on 2026-06-25 ended in real character death (most likely Hover Pack charge running out at altitude — there was no usable `death_screen` template at the time, so the cause couldn't be confirmed from screenshots). Fixed since:
  - `templates/death_screen.png` is now a real template, cropped from that actual death screen ("Press RMB to Respawn" banner). Real death frames score 0.75-1.0 against it; normal gameplay scores ~0.25 — threshold set to 0.60 in `config.toml`.
  - `handle_death_respawn` no longer depends on a `respawn_button` template (it never existed). Respawning is a global right-click ("Press RMB to Respawn"), not a clickable button at a fixed position — and the right-click was silently ignored until the cursor was re-centered (it had drifted to the screen edge from an earlier UI interaction). `inp.respawn_confirm()` now centers the cursor first, and the activity retries once and verifies via `death_screen` before giving up.
  - `explore_leg` now runs each leg in `check_interval_seconds`-sized chunks (default 1.0s) instead of one long blind hold, checking health/death and saving a screenshot after **every** chunk, stopping immediately on death. Previously a single uninterrupted ~3.5s hold was the entire gap in which the death above happened, with no checkpoint inside it to pin down the cause.
  - `[exploration] ascend_every_chunks`/`ascend_pulse_seconds`: optional periodic short `space` taps interleaved with movement, for "stay as high as possible without leaving Hover Pack charge range" flight, instead of holding `space` continuously (which is harder to judge against the charge gauge).
- **Blind navigation:** The bot uses fixed-duration key presses to walk. If the character collides with something or gets pushed by an enemy, the route can drift. Temporal handles this through the failed-activity retry flow.
- **Mobile combat:** Target tracking is reactive and works best against slow enemies. Fast enemies (like agile Spitters) may require more ammo.
- **Window focus on Wayland:** `focus_game()` uses `xdotool windowfocus`, which reports success but can't actually bring the game window to the foreground in native Wayland sessions (KWin's focus-stealing protection) — it only works if the game is already focused. Since the `uinput` virtual mouse sends input to whatever currently has focus (not to a specific window), **the Satisfactory window needs to stay in the foreground for the entire duration of a workflow run** — avoid switching to another window (ex: a terminal) while a workflow is running.
- **Mouse-look (resolved via uinput):** `move_mouse_relative`/`aim_at_screen_position` rotate the camera through a virtual mouse created with `evdev`/`uinput` (`/dev/uinput`), no longer via `pynput`/X11-XTest. This was necessary because the game runs via Proton/Wine, and the game's Raw Input completely ignores synthetic relative motion injected via X11/XTest — even confirming that the real desktop cursor moves (tested with `Xlib.ext.xtest.fake_input(detail=True)`), the in-game camera didn't react. A `uinput` mouse shows up as a physical device to the kernel/`libinput`, and Wine/Proton reads Raw Input correctly from it. Requires `/dev/uinput` to have a `uaccess` ACL for the session user — on distros with default udev rules for KDE Connect, Steam Input, or antimicrox (`TAG+="uaccess"` on `uinput`), this already works with no extra setup; otherwise, a custom udev rule is needed.
- **Hazard enemies (area damage):** The Nuclear Cliff Hog (radiation) and Elite Gas Stinger (poison gas) aren't engaged by the normal combat loop — the bot retreats (`retreat_from_hazard`) instead of trying to kill them, since the static aim-and-shoot isn't safe against area damage.
- **Resource harvesting:** `ResourceHarvestWorkflow` doesn't navigate to the node — the player needs to manually position the character within interaction range before triggering the workflow.
- **Combat expedition:** `CombatExpeditionWorkflow` depends on manually calibrated `[locations.*]` for each zone — without that, "blind" navigation can end up anywhere. Loot deposit via `open_storage_and_deposit_loot` is best-effort (shift-click across the whole inventory grid, without confirming the transfer) and the ammo reading via OCR can fail silently (returns -1, and the workflow doesn't block combat in that case).
- **Doggo taming:** `TameDoggoWorkflow` is best-effort. The visual success cue (the Doggo eating, jumping, and "squeaking") is too weak for reliable template matching — the workflow only records that it offered the berry, not that taming actually worked. Review the screenshots in `debug_screenshots/` manually.
- **Screen resolution:** Templates captured at a specific resolution (ex: 1920x1080) are specific to it. If you change the game's resolution, recapture them.
- **Out of scope (not automatable with this architecture):** Hard Drives and Somersloops require navigating an open map with no pathfinding (fixed but distant locations, often behind logistics prerequisites); building requires free-aim with real-time visual feedback from the Build Gun; exploring Power Slugs/Mercer Spheres has no fixed UI prompt to anchor detection on. None of these are feasible with template-matching vision + fixed keyboard macros.
