"""
activities/game_activities.py

Temporal activities — atomic actions in the game.

Conventions:
- Typed exceptions (VisionError, NavigationError, MenuError) show up
  descriptively in Temporal's history.
- Long-running activities call activity.heartbeat() periodically to
  avoid a false Temporal timeout.
- screenshot_on_error: any unhandled exception automatically saves a
  screenshot before propagating.
- FIXED BUG: check_health_low wasn't being called as an activity from
  inside engage_enemy (you can't call an activity from inside an
  activity). It now uses _check_health_inline(), which accesses Vision
  directly.
"""
import time
import logging
from contextlib import contextmanager
from typing import Optional
from temporalio import activity

from utils.vision import Vision, MatchResult
from utils.screenshot import save_debug_screenshot
from utils.exceptions import VisionError, NavigationError, MenuError, RespawnError
from utils import config as cfg
from utils import input as inp
from utils import stats as stats_module

logger = logging.getLogger(__name__)

_vision: Vision | None = None


def get_vision() -> Vision:
    global _vision
    if _vision is None:
        _vision = Vision()
    return _vision


@contextmanager
def screenshot_on_error(label: str):
    """Saves a screenshot if the activity raises an exception."""
    try:
        yield
    except Exception as exc:
        path = save_debug_screenshot(f"error_{label}")
        logger.error("[%s] %s: %s | screenshot: %s", label, type(exc).__name__, exc, path)
        raise


def _check_health_inline(v: Vision, frame=None) -> bool:
    """
    Checks health directly via Vision — no Temporal dispatch.
    Used inside engage_enemy (you can't call another activity from
    inside an activity; using the decorator would just call the local
    function, not a new Temporal execution).

    Accepts an already-captured frame to avoid grabbing the screen again
    (each capture can be slow on this system, especially if mss falls
    back to the ImageMagick subprocess — see explore_leg, which captures
    once and reuses the frame for the screenshot and every check).
    """
    result = v.find("health_low_indicator", frame=frame)
    if result.found:
        logger.warning("Low health detected (conf=%.2f).", result.confidence)
    return result.found


# ---------------------------------------------------------------------------
# Activity: Screenshot
# ---------------------------------------------------------------------------

@activity.defn
async def take_debug_screenshot(label: str = "manual") -> str:
    """Takes an immediate screenshot. Can be called from any workflow."""
    path = save_debug_screenshot(label)
    logger.info("Screenshot: %s", path)
    return str(path)


# ---------------------------------------------------------------------------
# Activity: Persist Stats
# ---------------------------------------------------------------------------

@activity.defn
async def persist_session_stats(workflow_type: str, stats: dict) -> str:
    """Saves session stats to stats/ at the end of the workflow."""
    path = stats_module.save(workflow_type, stats)
    logger.info("Stats saved: %s", path)
    return str(path)


# ---------------------------------------------------------------------------
# Activities: Gifts and Inventory
# ---------------------------------------------------------------------------

def _face_doggo_and_recheck(v: Vision) -> MatchResult:
    """
    If 'gift_prompt' isn't visible, looks for a Doggo on screen ('doggo_body')
    and aims/steps toward it so the 'E' interact prompt has a chance to show
    up, instead of requiring the player to already be looking straight at it.
    Lizard Doggos near the pen barely move, so a small bounded mouse sweep
    (left, past center to the right, back to center) plus a short step
    forward is enough to bring one into frame.
    """
    disp = cfg.get("display", {})
    sw = disp.get("screen_width", 1920)
    sh = disp.get("screen_height", 1080)
    center_x, center_y = sw // 2, sh // 2

    doggo_threshold = cfg.get("vision.thresholds.doggo_body", 0.62)
    doggo = v.find("doggo_body", threshold=doggo_threshold)

    if not doggo.found:
        for dx in cfg.get("taming.search_sweep_dx", [-400, 800, -400]):
            inp.move_mouse_relative(dx, 0)
            time.sleep(0.3)
            doggo = v.find("doggo_body", threshold=doggo_threshold)
            if doggo.found:
                break

    if not doggo.found:
        return v.find("gift_prompt")

    logger.debug("Doggo spotted at (%d,%d) conf=%.2f — aiming.", doggo.x, doggo.y, doggo.confidence)
    inp.aim_at_screen_position(doggo.x, doggo.y, center_x, center_y)
    time.sleep(0.2)
    inp.move_forward(0.3)
    time.sleep(0.2)
    return v.find("gift_prompt")


@activity.defn
async def collect_doggo_gift() -> bool:
    """
    Interacting with a Lizard Doggo opens the Doggo's own ONE-slot loot
    window — not the player's inventory. We wait for 'doggo_loot_window'
    (not 'inventory_open'). Doggos with no item only have a ~0.2%/s chance
    of finding something (~8min average), so most interactions will find
    an empty window — that's expected, not a failure.
    """
    with screenshot_on_error("collect_doggo_gift"):
        v = get_vision()
        result = v.find("gift_prompt")

        if not result.found:
            result = _face_doggo_and_recheck(v)

        if not result.found:
            logger.debug("No gift (conf=%.2f)", result.confidence)
            return False

        logger.info("Gift at (%d,%d) conf=%.2f — collecting.", result.x, result.y, result.confidence)
        inp.interact()

        confirm = v.wait_for("doggo_loot_window", timeout=3.0)
        if confirm.found:
            time.sleep(0.3)
            inp.close_menu()
            logger.info("Gift collected.")
            return True

        raise MenuError("Doggo loot window did not open after interacting")


@activity.defn
async def check_inventory_full() -> bool:
    v = get_vision()
    result = v.find("inventory_full_indicator")
    logger.debug("Inventory full: %s (conf=%.2f)", result.found, result.confidence)
    return result.found


@activity.defn
async def check_health_low() -> bool:
    """Checks for low health. When called from a workflow, uses normal Temporal dispatch."""
    return _check_health_inline(get_vision())


# ---------------------------------------------------------------------------
# Activities: Lizard Doggo Taming
# ---------------------------------------------------------------------------

@activity.defn
async def feed_wild_doggo() -> bool:
    """
    Attempts to tame a wild Lizard Doggo: opens the inventory, drags a
    Paleberry to a fixed screen point (drops it in the world, near the
    player) and closes the inventory.

    The success cue (Doggo eats, jumps, and "squeaks") is a weak visual
    signal and isn't verified here — best-effort. Doggos compete for the
    same berry, which is why the workflow calls this activity multiple
    times.
    """
    with screenshot_on_error("feed_wild_doggo"):
        v = get_vision()
        wild = v.find("wild_doggo_prompt")
        if not wild.found:
            logger.debug("No wild Doggo in sight (conf=%.2f)", wild.confidence)
            return False

        inp.open_inventory()
        berry = v.wait_for("paleberry_icon", timeout=2.0)
        if not berry.found:
            inp.close_menu()
            raise VisionError(
                "paleberry_icon", berry.confidence,
                cfg.get("vision.thresholds.paleberry_icon", 0.85)
            )

        taming = cfg.get("taming", {})
        drop_x = taming.get("drop_point_x", 1280)
        drop_y = taming.get("drop_point_y", 720)
        inp.drag(berry.x, berry.y, drop_x, drop_y)
        time.sleep(0.3)
        inp.close_menu()

        logger.info("Paleberry offered to the wild Doggo (conf=%.2f).", wild.confidence)
        return True


# ---------------------------------------------------------------------------
# Activities: Ammo Crafting
# ---------------------------------------------------------------------------

@activity.defn
async def navigate_to_location(location: str) -> bool:
    """
    Navigates to a named location in config.toml [locations.<location>]:
    runs the fixed key/duration sequence (steps) and, if the location has
    an 'arrival_template', confirms arrival via vision.

    Generalizes the pattern used by navigate_to_equipment_workshop to
    arbitrary locations (combat zones, storage, etc.) without needing a
    dedicated activity for each one.
    """
    with screenshot_on_error(f"navigate_to_{location}"):
        loc = cfg.get(f"locations.{location}")
        if not loc:
            raise NavigationError(
                f"Location '{location}' not defined in config.toml [locations.{location}]."
            )

        steps = loc.get("steps", [])
        logger.info("Navigating to '%s' (%d step(s))...", location, len(steps))
        for i, step in enumerate(steps):
            activity.heartbeat(f"step {i + 1}/{len(steps)} of '{location}'")
            inp.hold(step["key"], step.get("duration", 0.5))

        arrival_template = loc.get("arrival_template")
        if arrival_template:
            v = get_vision()
            result = v.wait_for(arrival_template, timeout=loc.get("arrival_timeout", 5.0))
            if not result.found:
                raise NavigationError(
                    f"Arrival at '{location}' not confirmed — template "
                    f"'{arrival_template}' not found. Adjust [locations.{location}] in config.toml."
                )

        logger.info("Arrival at '%s' complete.", location)
        return True


@activity.defn
async def navigate_to_equipment_workshop() -> bool:
    """
    Navigates to the Equipment Workshop via the key sequence configured in
    config.toml. If it fails, adjust [navigation] in config.toml.
    """
    with screenshot_on_error("navigate_to_workshop"):
        nav = cfg.get("navigation", {})
        logger.info("Navigating to the Equipment Workshop...")
        activity.heartbeat("starting navigation")

        inp.move_forward(nav.get("to_workshop_forward_1", 1.2))
        activity.heartbeat("walking forward (1)")
        inp.strafe_right(nav.get("to_workshop_strafe_right", 0.8))
        inp.move_forward(nav.get("to_workshop_forward_2", 0.5))

        v = get_vision()
        result = v.wait_for("equipment_workshop_prompt", timeout=5.0)
        if not result.found:
            raise NavigationError(
                "Equipment Workshop not found after navigation. "
                "Adjust [navigation] in config.toml."
            )

        logger.info("Workshop at (%d,%d).", result.x, result.y)
        return True


@activity.defn
async def check_ammo_count() -> int:
    """
    Reads the ammo count from the HUD via OCR (region configurable in
    config.toml [combat.ammo_region]). Returns -1 if the reading fails or
    the region isn't calibrated — the workflow treats -1 as "unknown" and
    doesn't block combat because of it.
    """
    v = get_vision()
    region = cfg.get("combat.ammo_region", {})
    text = v.read_text_region(
        region.get("x", 0), region.get("y", 0),
        region.get("w", 80), region.get("h", 40),
    )
    try:
        count = int(text)
        logger.debug("Ammo detected: %d", count)
        return count
    except ValueError:
        logger.warning("Failed to read ammo count (OCR returned '%s').", text)
        return -1


@activity.defn
async def craft_rifle_ammo(quantity: int = 50) -> int:
    with screenshot_on_error("craft_rifle_ammo"):
        v = get_vision()

        inp.interact()
        activity.heartbeat("waiting for workshop menu")
        if not v.wait_for("workshop_menu_open", timeout=4.0).found:
            raise MenuError("Workshop menu did not open")

        ammo_icon = v.find("rifle_ammo_icon")
        if not ammo_icon.found:
            inp.close_menu()
            r = ammo_icon
            raise VisionError("rifle_ammo_icon", r.confidence,
                               cfg.get("vision.thresholds.rifle_ammo_icon", 0.85))

        inp.click(ammo_icon.x, ammo_icon.y)
        time.sleep(0.2)

        craft_btn = v.find("craft_button")
        if not craft_btn.found:
            inp.close_menu()
            raise VisionError("craft_button", craft_btn.confidence,
                               cfg.get("vision.thresholds.craft_button", 0.87))

        activity.heartbeat(f"crafting {quantity} unit(s)")
        from pynput.mouse import Controller as _MC, Button as _Btn
        _m = _MC()
        _m.position = (craft_btn.x, craft_btn.y)
        _m.press(_Btn.left)
        time.sleep(0.05 * quantity)
        _m.release(_Btn.left)

        time.sleep(0.5)
        inp.close_menu()

        logger.info("Crafted ~%d Rifle Ammo.", quantity)
        return quantity


@activity.defn
async def harvest_resource_node(swings: int = 20) -> int:
    """
    Harvests a resource node (manual pickaxe or a node already opened up by
    a Nobelisk) by repeatedly pressing interact. Assumes the player is
    already positioned within range — there's no navigation to the node;
    that positioning is done manually once, like at the Workshop.
    """
    with screenshot_on_error("harvest_resource_node"):
        v = get_vision()
        check = v.find("resource_node_prompt")
        if not check.found:
            raise VisionError(
                "resource_node_prompt", check.confidence,
                cfg.get("vision.thresholds.resource_node_prompt", 0.80)
            )

        interval = cfg.get("harvesting.swing_interval_seconds", 0.5)
        count = 0
        for i in range(swings):
            activity.heartbeat(f"harvesting {i + 1}/{swings}")
            inp.interact()
            time.sleep(interval)
            count += 1

        logger.info("Harvest complete: %d interaction(s) on the node.", count)
        return count


@activity.defn
async def open_storage_and_deposit_loot() -> int:
    """
    Opens a storage container (needs the interaction prompt in range) and
    sweeps the player's inventory grid with a shift-click on every slot to
    transfer everything at once. Shift-clicking an empty slot does
    nothing, so it's safe to sweep the whole grid without detecting items
    one by one.

    Best-effort: confirms the storage opened, but doesn't verify the
    items were actually transferred. Calibrate [inventory_grid] in
    config.toml with the real coordinates of your inventory layout/resolution.
    """
    with screenshot_on_error("open_storage_and_deposit_loot"):
        v = get_vision()
        prompt = v.find("storage_prompt")
        if not prompt.found:
            raise VisionError(
                "storage_prompt", prompt.confidence,
                cfg.get("vision.thresholds.storage_prompt", 0.82)
            )

        inp.interact()
        opened = v.wait_for("storage_open", timeout=3.0)
        if not opened.found:
            raise MenuError("Storage window did not open after interacting")

        grid = cfg.get("inventory_grid", {})
        origin_x = grid.get("origin_x", 100)
        origin_y = grid.get("origin_y", 100)
        slot_w = grid.get("slot_w", 90)
        slot_h = grid.get("slot_h", 90)
        columns = grid.get("columns", 10)
        rows = grid.get("rows", 4)

        slots_clicked = 0
        for row in range(rows):
            activity.heartbeat(f"row {row + 1}/{rows} of the inventory")
            for col in range(columns):
                inp.shift_click(origin_x + col * slot_w, origin_y + row * slot_h)
                slots_clicked += 1

        time.sleep(0.3)
        inp.close_menu()
        logger.info("Storage: %d slot(s) swept with shift-click.", slots_clicked)
        return slots_clicked


@activity.defn
async def navigate_back_to_base() -> bool:
    """
    Returns to the farming spot. Verifies the character actually left the
    Workshop area (if the prompt is still visible, the movement had no
    effect — collision, obstruction, etc).
    """
    with screenshot_on_error("navigate_back_to_base"):
        nav = cfg.get("navigation", {})
        inp.move_backward(nav.get("back_to_base_backward_1", 1.2))
        inp.strafe_left(nav.get("back_to_base_strafe_left", 0.8))
        inp.move_backward(nav.get("back_to_base_backward_2", 0.5))

        v = get_vision()
        if v.find("equipment_workshop_prompt").found:
            raise NavigationError(
                "Still inside the Equipment Workshop area after navigating back. "
                "The character may be obstructed. Adjust [navigation] in config.toml."
            )
        return True


# ---------------------------------------------------------------------------
# Activities: Combat and Loot
# ---------------------------------------------------------------------------

# Variants that deal area damage (radiation/gas) — engage_enemy's static
# aim-and-shoot loop wasn't designed for this. Workflows should treat
# "hazard" as a signal to retreat instead of engaging normally.
HAZARD_ENEMY_TYPES = {"enemy_hog_nuclear", "enemy_stinger_elite_gas"}


@activity.defn
async def scan_for_enemy() -> dict:
    v = get_vision()
    result = v.find_enemy()

    if result:
        hazard = result.template_name in HAZARD_ENEMY_TYPES
        logger.info(
            "Enemy '%s' at (%d,%d) conf=%.2f hazard=%s",
            result.template_name, result.x, result.y, result.confidence, hazard
        )
        return {
            "found": True,
            "x": result.x,
            "y": result.y,
            "confidence": result.confidence,
            "type": result.template_name,
            "hazard": hazard,
        }

    return {"found": False, "x": 0, "y": 0, "confidence": 0.0, "type": "", "hazard": False}


@activity.defn
async def retreat_from_hazard() -> bool:
    """
    Retreats without engaging — used when scan_for_enemy signals 'hazard'
    (a radiation/gas area-damage variant). engage_enemy's static
    aim-and-shoot loop isn't safe against these variants.
    """
    inp.move_backward(1.5)
    inp.dodge()
    logger.warning("Retreating from a hazard enemy (area damage) without engaging.")
    return True


@activity.defn
async def engage_enemy(
    target_x: int,
    target_y: int,
    screen_w: Optional[int] = None,
    screen_h: Optional[int] = None,
) -> str:
    """
    Engages an enemy at (target_x, target_y).
    Combat parameters come from config.toml[combat].
    Returns: 'killed' | 'escaped' | 'died'
    """
    with screenshot_on_error("engage_enemy"):
        v = get_vision()
        disp = cfg.get("display", {})
        sw = screen_w or disp.get("screen_width", 1920)
        sh = screen_h or disp.get("screen_height", 1080)
        center_x, center_y = sw // 2, sh // 2
        max_dur = cfg.get("combat.max_combat_duration_seconds", 10.0)

        logger.info("Engaging enemy at (%d,%d)", target_x, target_y)
        inp.aim_at_screen_position(target_x, target_y, center_x, center_y)
        time.sleep(0.1)

        combat_start = time.time()
        bursts_fired = 0

        while time.time() - combat_start < max_dur:
            activity.heartbeat(f"combat — {bursts_fired} bursts")

            # _check_health_inline avoids calling another activity from inside an activity
            if _check_health_inline(v):
                logger.warning("Low health — fleeing.")
                inp.dodge()
                inp.move_backward(1.0)
                return "escaped"

            inp.shoot()
            bursts_fired += 1
            time.sleep(0.1)

            enemy = v.find_enemy()
            if not enemy:
                logger.info("Enemy eliminated after %d bursts.", bursts_fired)
                break

            inp.aim_at_screen_position(enemy.x, enemy.y, center_x, center_y)

        if v.find("death_screen").found:
            save_debug_screenshot("player_death")
            logger.error("Character died during combat.")
            return "died"

        time.sleep(0.8)
        remains = v.find("enemy_remains_prompt")
        if remains.found:
            inp.loot_remains()
            if v.wait_for("inventory_open", timeout=3.0).found:
                time.sleep(0.4)
                inp.close_menu()
                logger.info("Loot collected.")

        return "killed"


@activity.defn
async def handle_death_respawn() -> bool:
    """
    Confirms 'Press RMB to Respawn'. This isn't a clickable UI button at a
    fixed position (no 'respawn_button' template exists) — it's a global
    right-click action, confirmed live on 2026-06-25 from an actual death.
    Retries once since the cursor drifting to the screen edge from earlier
    UI interactions can cause the first attempt to be silently ignored.
    """
    with screenshot_on_error("handle_death_respawn"):
        v = get_vision()
        inp.respawn_confirm()
        time.sleep(3.0)

        if v.find("death_screen").found:
            logger.warning("Still on death screen after first respawn attempt — retrying.")
            inp.respawn_confirm()
            time.sleep(3.0)

        if v.find("death_screen").found:
            save_debug_screenshot("respawn_failed")
            raise RespawnError("Death screen still showing after two respawn attempts.")

        logger.info("Respawned.")
        return True


@activity.defn
async def capture_template_screen(screen_name: str, key_to_open: str = "", key_to_close: str = "") -> str:
    """Focuses the game, sends the command to open, captures the screen, and closes the menu."""
    import time
    from utils.screenshot import save_debug_screenshot

    inp.focus_game("Satisfactory")
    time.sleep(0.5)

    if key_to_open:
        inp.press(key_to_open)
        time.sleep(0.8)  # wait for the opening animation

    v = get_vision()
    frame = v.capture()
    path = save_debug_screenshot(screen_name, frame=frame)
    logger.info("Screen captured for calibration: %s", path)

    if key_to_close:
        inp.press(key_to_close)
        time.sleep(0.3)

    return str(path)


@activity.defn
async def extract_templates_from_screen(screenshot_path: str, target: str = "hud", resolution: str = "2560x1440") -> dict:
    """Extracts regions of interest from the capture and saves them as new PNG templates."""
    import cv2
    from pathlib import Path

    path = Path(screenshot_path)
    if not path.exists():
        raise FileNotFoundError(f"Capture not found: {screenshot_path}")

    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"Failed to load image: {screenshot_path}")

    h, w = img.shape[:2]
    logger.info("Extracting templates for target '%s' and resolution %dx%d (config: %s)", target, w, h, resolution)

    templates_dir = Path("templates")
    templates_dir.mkdir(exist_ok=True)

    results = {}

    # Coordinates mapped for 2560x1440, with a proportional fallback
    if target == "hud":
        if w == 2560 and h == 1440:
            coords = {
                "health_low_indicator": (1330, 1380, 70, 120),   # Heart icon (health)
                "inventory_open": (1215, 1265, 2185, 2245),       # Tab icon in the HUD
            }
        else:
            coords = {
                "health_low_indicator": (int(h * 0.923), int(h * 0.958), int(w * 0.027), int(w * 0.047)),
                "inventory_open": (int(h * 0.843), int(h * 0.878), int(w * 0.853), int(w * 0.877)),
            }
    elif target == "workshop":
        # Note: temporary calibration coordinates for the Equipment Workshop at 2560x1440
        if w == 2560 and h == 1440:
            coords = {
                "workshop_menu_open": (50, 150, 100, 400),       # Workshop menu title (top-left)
                "rifle_ammo_icon": (400, 600, 300, 500),         # Rifle ammo icon in the menu
                "craft_button": (1000, 1200, 1800, 2200),        # Craft button (hold to fabricate)
            }
        else:
            coords = {
                "workshop_menu_open": (int(h * 0.034), int(h * 0.104), int(w * 0.039), int(w * 0.156)),
                "rifle_ammo_icon": (int(h * 0.277), int(h * 0.416), int(w * 0.117), int(w * 0.195)),
                "craft_button": (int(h * 0.694), int(h * 0.833), int(w * 0.703), int(w * 0.859)),
            }
    else:
        raise ValueError(f"Unknown extraction target: {target}")

    for name, (y1, y2, x1, x2) in coords.items():
        cropped = img[y1:y2, x1:x2]
        out_path = templates_dir / f"{name}.png"
        cv2.imwrite(str(out_path), cropped)
        results[name] = str(out_path)
        logger.info("Template '%s' extracted and saved to %s", name, out_path)

    return results


@activity.defn
async def reset_to_safe_state() -> bool:
    """
    Defensive cleanup: closes any open menu (gift, inventory, workshop).
    Called when cancelling/ending a workflow so the game isn't left with
    an open menu between one session and the next.
    """
    inp.close_menu()
    time.sleep(0.2)
    inp.close_menu()
    logger.info("Safe state restored (menus closed).")
    return True


# ---------------------------------------------------------------------------
# Activities: Exploration (blind traversal + screenshot collection)
# ---------------------------------------------------------------------------

def _died_inline(v: Vision, frame=None) -> bool:
    """
    Best-effort death check for exploration legs. Unlike engage_enemy
    (which treats a missing 'death_screen' template as a bug to surface),
    here we treat it the same way check_ammo_count treats a failed OCR
    read: "unknown, don't block" — losing screen visibility into death
    shouldn't make autonomous exploration crash instead of returning home.
    """
    try:
        return v.find("death_screen", frame=frame).found
    except FileNotFoundError:
        return False


@activity.defn
async def get_exploration_route() -> dict:
    """Reads [exploration] from config.toml — config/file I/O must happen in an activity, not in workflow code (the Temporal sandbox forbids `open()` there)."""
    return {
        "route": cfg.get("exploration.route", []),
        "max_total_duration_seconds": cfg.get("exploration.max_total_duration_seconds", 25.0),
        "check_interval": cfg.get("exploration.check_interval_seconds", 1.0),
        "ascend_every": cfg.get("exploration.ascend_every_chunks", 0),
        "ascend_pulse": cfg.get("exploration.ascend_pulse_seconds", 0.3),
    }


@activity.defn
async def capture_base_reference() -> str:
    """
    Snapshots the character's current position as the 'base' reference
    point for an exploration run — assumes the player is at/near base when
    this is called (true for an AFK session). Used only as a visual record
    of the starting point; ExplorationWorkflow returns via the mirrored
    key sequence, not via image matching against this screenshot.
    """
    inp.focus_game("Satisfactory")
    time.sleep(0.2)
    path = save_debug_screenshot("base_reference")
    logger.info("Base reference captured: %s", path)
    return str(path)


@activity.defn
async def explore_leg(
    keys: list[str],
    duration: float,
    turn_dx: int = 0,
    leg_index: int = 0,
    check_interval: float = 1.0,
    ascend_every: int = 0,
    ascend_pulse: float = 0.3,
) -> dict:
    """
    Runs one leg of an exploration route: turns the camera by turn_dx,
    then holds `keys` simultaneously (ex: ["w", "space"] to advance while
    holding jump for Hover Pack ascend/glide), in `check_interval`-sized
    chunks instead of one long blind hold — checking health/death and
    saving a screenshot after EVERY chunk, stopping immediately if death
    is detected.

    Built after a live death during a single 3.5s uninterrupted 'w' hold
    on 2026-06-25: the only health/death checks were before and after
    that hold, so the cause of death couldn't be pinned down from the
    screenshots — there was no checkpoint inside the window where it
    happened. Sub-second-to-1s chunks close that gap.

    ascend_every (if >0): taps space for ascend_pulse seconds every N
    chunks, interleaved with movement, to counter altitude loss while
    flying — independent of whether 'space' is already in `keys`.

    Re-focuses the game window before every leg — input is otherwise
    silently swallowed by whatever window happens to have focus (ex: the
    terminal running this worker), which can make a whole route a no-op
    without raising any error (confirmed live on 2026-06-25: a full route
    produced identical before/after screenshots until focus was restored).
    """
    with screenshot_on_error(f"explore_leg_{leg_index}"):
        v = get_vision()
        inp.focus_game("Satisfactory")
        time.sleep(0.15)

        if turn_dx:
            inp.move_mouse_relative(turn_dx, 0)
            time.sleep(0.15)

        elapsed = 0.0
        chunk_index = 0
        died = False
        health_low = False
        screenshots: list[str] = []

        while elapsed < duration:
            activity.heartbeat(f"leg {leg_index} chunk {chunk_index}")
            chunk = min(check_interval, duration - elapsed)

            if ascend_every > 0 and chunk_index > 0 and chunk_index % ascend_every == 0:
                inp.hold_keys(["space"], ascend_pulse)
                time.sleep(0.05)

            inp.hold_keys(keys, chunk)
            elapsed += chunk

            # One capture reused for the screenshot and both checks — each
            # capture can be slow (mss occasionally falls back to spawning
            # an ImageMagick subprocess).
            frame = v.capture()
            path = save_debug_screenshot(f"explore_leg_{leg_index}_{chunk_index}", frame=frame)
            screenshots.append(str(path))
            health_low = _check_health_inline(v, frame=frame)
            died = _died_inline(v, frame=frame)

            logger.info(
                "Leg %d chunk %d: keys=%s elapsed=%.1f/%.1fs turn_dx=%d health_low=%s died=%s screenshot=%s",
                leg_index, chunk_index, keys, elapsed, duration, turn_dx, health_low, died, path,
            )
            chunk_index += 1
            # Heartbeat after each chunk's work too, not just before — a
            # single chunk's capture+checks took ~9s live on this system
            # (mss falling back to its slow ImageMagick subprocess path),
            # which is close enough to a 10s heartbeat_timeout that only
            # heartbeating at the top of the loop let the activity time
            # out anyway (confirmed live 2026-06-25).
            activity.heartbeat(f"leg {leg_index} chunk {chunk_index} done")

            if died:
                logger.warning("Death detected mid-leg (chunk %d) — stopping this leg immediately.", chunk_index)
                break

        return {
            "keys": keys,
            "duration": elapsed,
            "turn_dx": turn_dx,
            "health_low": health_low,
            "died": died,
            "screenshots": screenshots,
        }


@activity.defn
async def return_via_reverse_route(legs_taken: list[dict]) -> bool:
    """
    Retraces legs_taken in reverse order with mirrored keys (w<->s, a<->d;
    'space' passes through unchanged) and mirrored turns, to head back
    toward the start of an exploration run. Same blind-navigation idiom as
    navigate_back_to_base — approximate, not vision-verified.
    """
    with screenshot_on_error("return_via_reverse_route"):
        inp.focus_game("Satisfactory")
        time.sleep(0.2)
        logger.info("Returning via %d reversed leg(s)...", len(legs_taken))
        for i, leg in enumerate(reversed(legs_taken)):
            activity.heartbeat(f"return step {i + 1}/{len(legs_taken)}")
            reversed_keys = inp.opposite_keys(leg["keys"])
            inp.hold_keys(reversed_keys, leg["duration"])
            if leg["turn_dx"]:
                inp.move_mouse_relative(-leg["turn_dx"], 0)
                time.sleep(0.15)

        path = save_debug_screenshot("back_at_base")
        logger.info("Return sequence complete. Screenshot: %s", path)
        return True


@activity.defn
async def verify_matching_templates(template_names: list[str]) -> dict:
    """Scans the current screen for the templates and returns the confidence status."""
    v = get_vision()
    results = v.scan_all(template_names)

    report = {}
    for name, r in results.items():
        report[name] = {
            "found": r.found,
            "x": r.x,
            "y": r.y,
            "confidence": float(r.confidence),
        }
        logger.info("Verification of '%s': found=%s, conf=%.3f", name, r.found, r.confidence)
    return report
