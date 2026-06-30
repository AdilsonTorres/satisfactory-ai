"""
activities/inventory.py

Inventory and Doggo gift activities.
"""

import logging
import time

import cv2
import numpy as np
from temporalio import activity

from utils import config as cfg
from utils import input as inp
from utils.exceptions import MenuError, VisionError
from utils.vision import MatchResult, Vision

from ._shared import get_vision, screenshot_on_error

logger = logging.getLogger(__name__)

# How many recapture+key attempts before giving up on a UI opening. UE5
# drops keyboard input until the viewport regains mouse capture, and a
# single recapture click only restores it ~50-65% of the time, so we verify
# the target template and retry. Detection is crisp (~0.98 open vs ~0.45
# closed), so 5 attempts gives >98% effective reliability.
_OPEN_WINDOW_ATTEMPTS = 5


def _press_until_window_open(
    v: Vision,
    template: str,
    key_action=inp.interact,
) -> MatchResult:
    """
    Recapture the game's mouse focus and press `key_action`, retrying until
    `template` is detected on screen or the attempt budget is exhausted.

    Returns the final MatchResult (check `.found`). Used wherever a keyboard
    press must open a UI: the press is silently swallowed unless the UE5
    viewport currently holds mouse capture, which `ensure_game_input_ready`
    only restores intermittently — verifying + retrying makes it reliable.
    """
    result = v.find(template)
    attempt = 0
    while not result.found and attempt < _OPEN_WINDOW_ATTEMPTS:
        attempt += 1
        inp.ensure_game_input_ready()
        key_action()
        time.sleep(0.8)
        result = v.find(template)
        logger.debug(
            "%s open attempt %d/%d: conf=%.2f found=%s",
            template, attempt, _OPEN_WINDOW_ATTEMPTS, result.confidence, result.found,
        )
    return result


def _gift_prompt_region(sw: int, sh: int) -> tuple[int, int, int, int]:
    """
    Screen rectangle where the 'Press E … Lizard Doggo …' prompt renders.

    The prompt is a UI band anchored to the crosshair, NOT to the Doggo's
    world position: it's horizontally centred and sits ~9% of the screen
    height below centre (measured live 2026-06-30 at 2560x1440: the 740x50
    band landed at x 920-1660, y 785-835). Returning a snug band lets us
    detect it with a ~0.2s cropped grab instead of a ~7.5s full frame.
    """
    cx = sw // 2
    cy = int(sh * 0.5625)
    half_w, margin_y = 540, 70
    x = max(0, cx - half_w)
    y = max(0, cy - margin_y)
    return (x, y, min(sw - x, 2 * half_w), min(sh - y, 2 * margin_y))


def _camera_responds(v: Vision) -> bool:
    """
    True if the gameplay camera actually turns when we send a relative mouse
    move. The virtual mouse only drives the camera while the game holds
    pointer capture; in a free-pointer state the same motion moves the menu
    cursor instead and the view is frozen (measured live: a 2500px yaw left
    the frame pixel-identical).

    We nudge yaw and measure the horizontal SHIFT of a central patch via
    phase correlation, recapturing once before giving up. Phase correlation
    is used instead of a frame difference because grass and the Doggo's idle
    animation make a plain abs-diff read ~13 even with the camera frozen
    (false 'moved'); a real yaw shows up as a coherent x-translation while
    in-place animation produces ~0 net shift (measured: frozen 0.01px).
    """
    disp = cfg.get("display", {})
    sw = disp.get("screen_width", 1920)
    sh = disp.get("screen_height", 1080)
    # A central patch grabbed with the fast cropped path (~0.2s); a full-frame
    # capture would cost ~7.5s per probe.
    px, py, pw, ph = sw // 2 - 300, sh // 2 - 200, 600, 400
    window = cv2.createHanningWindow((pw, ph), cv2.CV_32F)

    def _luma() -> np.ndarray:
        return cv2.cvtColor(v.grab_region(px, py, pw, ph), cv2.COLOR_BGR2GRAY).astype(np.float32)

    for attempt in range(2):
        before = _luma()
        inp.move_mouse_relative(300, 0)
        time.sleep(0.25)
        after = _luma()
        inp.move_mouse_relative(-300, 0)  # undo the probe
        time.sleep(0.15)
        (shift_x, _), _ = cv2.phaseCorrelate(before, after, window)
        if abs(shift_x) > 5.0:  # in-place animation reads ~0; a real turn shifts many px
            return True
        logger.debug("Camera probe %d: x-shift %.2fpx (frozen) — recapturing.", attempt, shift_x)
        inp.ensure_game_input_ready()
        time.sleep(0.2)
    return False


def _face_doggo_and_recheck(v: Vision) -> MatchResult:
    """
    Bring the 'gift_prompt' into view when it isn't already, by sweeping the
    camera until the interaction prompt appears.

    Uses 'gift_prompt' (a crisp, fixed-position UI band: ~0.8 present vs ~0.2
    absent) as the locator rather than the old 'doggo_body' world-crop, which
    matched ~0.5-0.6 everywhere — including a blank wall — and never reliably
    found the Doggo. The sweep walks PITCH as well as yaw because a Lizard
    Doggo is a ground creature: a yaw-only sweep with the camera pitched at
    the horizon misses it entirely. Bails early (and cheaply) if the camera
    isn't responding, and restores the original orientation if nothing is
    found, so a miss doesn't leave the view pointing at the ground.
    """
    disp = cfg.get("display", {})
    sw = disp.get("screen_width", 1920)
    sh = disp.get("screen_height", 1080)
    region = _gift_prompt_region(sw, sh)

    gp = v.find_in_region("gift_prompt", region)
    if gp.found:
        return gp

    if not _camera_responds(v):
        logger.warning("Camera not responding to mouse-look — cannot sweep for the Doggo.")
        return v.find_in_region("gift_prompt", region)

    # Grid sweep: a few downward pitch rows, each swept across yaw. Track the
    # net offset so we can undo it if the prompt never shows.
    yaw_step = int(cfg.get("taming.search_yaw_step", 180))
    yaw_count = int(cfg.get("taming.search_yaw_count", 8))
    pitch_rows = cfg.get("taming.search_pitch_rows", [0, 160, 160])

    net_pitch = 0
    try:
        for pitch in pitch_rows:
            if pitch:
                inp.move_mouse_relative(0, pitch)
                net_pitch += pitch
                time.sleep(0.2)
            net_yaw = 0
            for _ in range(yaw_count):
                gp = v.find_in_region("gift_prompt", region)
                if gp.found:
                    logger.info("Gift prompt acquired (conf=%.2f) after sweep.", gp.confidence)
                    return gp
                inp.move_mouse_relative(yaw_step, 0)
                net_yaw += yaw_step
                time.sleep(0.12)
            inp.move_mouse_relative(-net_yaw, 0)  # back to this row's yaw origin
            time.sleep(0.15)
    finally:
        if net_pitch:
            inp.move_mouse_relative(0, -net_pitch)  # restore original pitch
            time.sleep(0.15)

    return v.find_in_region("gift_prompt", region)


@activity.defn
async def collect_doggo_gift() -> bool:
    """
    Interacting with a Lizard Doggo opens the Doggo's own ONE-slot loot
    window — not the player's inventory (whether or not the Doggo found
    something). We wait for 'doggo_loot_window', then shift-click the
    item slot to transfer any gift to the player's inventory before
    closing. If the slot is empty the shift-click is a no-op.

    Doggos only find something ~0.2%/s (~8 min average), so most
    interactions open an empty window — that is expected, not a failure.
    """
    with screenshot_on_error("collect_doggo_gift"):
        v = get_vision()
        disp = cfg.get("display", {})
        region = _gift_prompt_region(
            disp.get("screen_width", 1920), disp.get("screen_height", 1080)
        )
        result = v.find_in_region("gift_prompt", region)

        if not result.found:
            result = _face_doggo_and_recheck(v)

        if not result.found:
            logger.debug("No gift prompt visible (conf=%.2f)", result.confidence)
            return False

        logger.info(
            "Gift prompt at (%d,%d) conf=%.2f — pressing E.",
            result.x, result.y, result.confidence,
        )
        # Pressing E only registers when the UE5 viewport holds mouse
        # capture, which a single recapture click restores intermittently,
        # so retry recapture+E until the loot window is confirmed open.
        confirm = _press_until_window_open(v, "doggo_loot_window")
        if not confirm.found:
            logger.warning(
                "Doggo loot window did not open after %d recapture+E "
                "attempts (conf=%.2f). Skipping this cycle.",
                _OPEN_WINDOW_ATTEMPTS, confirm.confidence,
            )
            return False

        # Window confirmed open — shift-click the item slot to transfer
        # the gift (if any) into the player's inventory. Coordinates come
        # from config.toml [taming] keys doggo_loot_slot_x / _y, which
        # are already calibrated for this display (2560x1440). Fall back
        # to an offset from the template match centre if not configured.
        slot_x = int(cfg.get("taming.doggo_loot_slot_x", confirm.x))
        slot_y = int(cfg.get("taming.doggo_loot_slot_y", confirm.y + 80))
        inp.shift_click(slot_x, slot_y)
        time.sleep(0.3)
        inp.close_menu()
        logger.info(
            "Doggo loot window closed (shift-clicked slot at %d,%d).",
            slot_x, slot_y,
        )
        return True


@activity.defn
async def check_inventory_full() -> bool:
    """
    Opens the player inventory (Tab), scans every slot's centre pixel
    for occupancy, optionally clicks the sort/merge button if all slots
    look occupied, then re-scans and closes the inventory.

    An inventory slot is considered EMPTY when the average brightness of
    a small patch around its centre is below `inventory.empty_slot_brightness`
    (default 35 out of 255 — Satisfactory's empty slots are near-black).

    Sort-button coordinates are read from config.toml
    [inventory_sort_button] x / y.  If those keys are absent the sort
    step is skipped and we rely on the first scan only.
    """
    v = get_vision()
    grid = cfg.get("inventory_grid", {})
    origin_x  = int(grid.get("origin_x", 100))
    origin_y  = int(grid.get("origin_y", 100))
    slot_w    = int(grid.get("slot_w", 90))
    slot_h    = int(grid.get("slot_h", 90))
    columns   = int(grid.get("columns", 10))
    rows      = int(grid.get("rows", 4))
    threshold = int(cfg.get("inventory.empty_slot_brightness", 35))
    patch     = 20  # half-width of the pixel patch; larger = more robust vs. item badges
    low_guard = 50   # below this is panel chrome (border/bg), not an empty slot

    def _count_empty(frame: np.ndarray) -> int:
        empty = 0
        h_max, w_max = frame.shape[:2]
        for row in range(rows):
            for col in range(columns):
                cx = origin_x + col * slot_w + slot_w // 2
                cy = origin_y + row * slot_h + slot_h // 2
                # Sample a larger patch and take median brightness (robust vs. badges)
                y0, y1 = max(0, cy - patch), min(h_max, cy + patch)
                x0, x1 = max(0, cx - patch), min(w_max, cx + patch)
                region = frame[y0:y1, x0:x1]
                if region.size == 0:
                    continue
                brightness = float(np.median(region))  # median avoids badge outliers
                # low_guard: panel borders read <50 — ignore them (not a slot at all)
                if low_guard <= brightness < threshold:
                    empty += 1
        return empty


    # Tab is swallowed unless the viewport holds mouse capture; retry
    # recapture+Tab until the inventory panel is confirmed open, otherwise
    # we'd scan the game world and mis-report "full".
    opened = _press_until_window_open(v, "inventory_open", key_action=inp.open_inventory)
    if not opened.found:
        logger.warning(
            "Inventory did not open after %d recapture+Tab attempts "
            "(conf=%.2f). Reporting not-full to avoid a false craft.",
            _OPEN_WINDOW_ATTEMPTS, opened.confidence,
        )
        return False
    time.sleep(0.3)  # let the panel finish rendering before sampling

    frame = v.capture()
    empty_count = _count_empty(frame)
    logger.debug("Inventory scan: %d empty slot(s) found.", empty_count)

    if empty_count > 0:
        inp.close_menu()
        logger.debug("Inventory has free space (%d empty). Not full.", empty_count)
        return False

    # All slots appear occupied — click the sort/merge button to consolidate
    # stacks (this can free slots by merging partial stacks of the same item).
    sort_x = cfg.get("inventory_sort_button.x", 0)
    sort_y = cfg.get("inventory_sort_button.y", 0)
    if sort_x and sort_y:
        logger.info("All slots occupied — clicking sort button at (%d,%d).", sort_x, sort_y)
        inp.click(int(sort_x), int(sort_y))
        time.sleep(0.5)
        frame = v.capture()
        empty_count = _count_empty(frame)
        logger.debug("Post-sort scan: %d empty slot(s).", empty_count)
    else:
        logger.debug(
            "inventory_sort_button not configured in config.toml — skipping sort step."
        )

    inp.close_menu()
    is_full = empty_count == 0
    logger.info("Inventory full: %s (empty slots after scan: %d).", is_full, empty_count)
    return is_full


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
            raise VisionError("storage_prompt", prompt.confidence, cfg.get("vision.thresholds.storage_prompt", 0.82))

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
            raise VisionError("paleberry_icon", berry.confidence, cfg.get("vision.thresholds.paleberry_icon", 0.85))

        taming = cfg.get("taming", {})
        drop_x = taming.get("drop_point_x", 1280)
        drop_y = taming.get("drop_point_y", 720)
        inp.drag(berry.x, berry.y, drop_x, drop_y)
        time.sleep(0.3)
        inp.close_menu()

        logger.info("Paleberry offered to the wild Doggo (conf=%.2f).", wild.confidence)
        return True
