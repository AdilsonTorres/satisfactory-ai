"""
utils/input.py
Sends mouse/keyboard input to Satisfactory on Linux.
Uses separate virtual mouse and virtual keyboard devices via uinput (evdev)
to bypass Proton and Wayland security filters.
X11 (pynput) is still used only to query and move the desktop cursor position absolutely.
"""

import atexit
import os
import subprocess
import tempfile
import time
from collections.abc import Sequence

from evdev import UInput
from evdev import ecodes as ev_codes
from pynput.mouse import Controller as MouseController

from utils import config as cfg

_mouse = MouseController()
_uinput_mouse: UInput | None = None
_uinput_keyboard: UInput | None = None


def _get_uinput_mouse() -> UInput:
    """
    Virtual mouse device via uinput — handles relative movement and button clicks.
    """
    global _uinput_mouse
    if _uinput_mouse is None:
        capabilities: dict[int, Sequence[int]] = {
            ev_codes.EV_REL: [ev_codes.REL_X, ev_codes.REL_Y, ev_codes.REL_WHEEL],
            ev_codes.EV_KEY: [ev_codes.BTN_LEFT, ev_codes.BTN_RIGHT],
        }
        _uinput_mouse = UInput(capabilities, name="satisfactory-bot-mouse")
        atexit.register(_uinput_mouse.close)
        time.sleep(0.3)  # give the compositor time to recognize the new device
    return _uinput_mouse


def _get_uinput_keyboard() -> UInput:
    """
    Virtual keyboard device via uinput — handles keyboard key presses.
    """
    global _uinput_keyboard
    if _uinput_keyboard is None:
        capabilities: dict[int, Sequence[int]] = {
            ev_codes.EV_KEY: list(range(1, 256)),
        }
        _uinput_keyboard = UInput(capabilities, name="satisfactory-bot-keyboard")
        atexit.register(_uinput_keyboard.close)
        time.sleep(1.0)  # give the compositor time to map the standard keyboard
    return _uinput_keyboard


# Map key names to evdev KEY codes
_KEY_CODE_MAP: dict[str, int] = {
    "escape": ev_codes.KEY_ESC,
    "tab": ev_codes.KEY_TAB,
    "enter": ev_codes.KEY_ENTER,
    "space": ev_codes.KEY_SPACE,
    "shift": ev_codes.KEY_LEFTSHIFT,
    "ctrl": ev_codes.KEY_LEFTCTRL,
    "alt": ev_codes.KEY_LEFTALT,
    "w": ev_codes.KEY_W,
    "a": ev_codes.KEY_A,
    "s": ev_codes.KEY_S,
    "d": ev_codes.KEY_D,
    "e": ev_codes.KEY_E,
    "f": ev_codes.KEY_F,
    "r": ev_codes.KEY_R,
    "q": ev_codes.KEY_Q,
}


def _resolve_key_code(key: str) -> int:
    name = key.lower()
    if name in _KEY_CODE_MAP:
        return _KEY_CODE_MAP[name]
    try:
        return int(getattr(ev_codes, f"KEY_{name.upper()}"))
    except AttributeError as err:
        raise ValueError(f"Unsupported uinput key: {key}") from err


# KWin (Wayland) input focus. On this KDE/Wayland session, xdotool/wmctrl only
# flip XWayland's EWMH "active window" flag — KWin does NOT treat that as input
# focus, so keyboard and relative mouse-look stay dead even though
# `getactivewindow` reports the game (verified live 2026-07-01). The ONLY thing
# that actually routes input to the game is asking KWin itself to activate the
# window via its scripting D-Bus API: a one-shot script that sets
# `workspace.activeWindow`. This restores both keys AND camera-look.
_KWIN_ACTIVATE_JS = """\
var wins = (typeof workspace.windowList === "function")
    ? workspace.windowList() : workspace.clientList();
for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    if ((w.caption || "").indexOf("%TITLE%") !== -1) {
        w.minimized = false;
        if ("activeWindow" in workspace) { workspace.activeWindow = w; }
        else { workspace.activeClient = w; }
        break;
    }
}
"""
_kwin_script_for: dict[str, str] = {}


def _qdbus_bin() -> str | None:
    for name in ("qdbus6", "qdbus"):
        if subprocess.run(["which", name], capture_output=True).returncode == 0:
            return name
    return None


def _kwin_activate(window_title: str) -> bool:
    """Give the game REAL KWin input focus via the KWin scripting D-Bus API.

    Writes (once per title) a temp JS script that sets workspace.activeWindow to
    the game window, then load+start it. Must unload first: loadScript with an
    already-registered pluginName is a no-op that never runs. Returns False if
    qdbus/KWin scripting isn't available (caller falls back to xdotool).
    """
    qdbus = _qdbus_bin()
    if qdbus is None:
        return False
    path = _kwin_script_for.get(window_title)
    if path is None or not os.path.exists(path):
        fd, path = tempfile.mkstemp(suffix=".js", prefix="kwin_activate_")
        with os.fdopen(fd, "w") as f:
            f.write(_KWIN_ACTIVATE_JS.replace("%TITLE%", window_title))
        _kwin_script_for[window_title] = path
    base = [qdbus, "org.kde.KWin", "/Scripting"]
    try:
        subprocess.run(
            [*base, "org.kde.kwin.Scripting.unloadScript", "sat-activate"],
            capture_output=True, timeout=3,
        )
        loaded = subprocess.run(
            [*base, "org.kde.kwin.Scripting.loadScript", path, "sat-activate"],
            capture_output=True, timeout=3,
        )
        subprocess.run(
            [*base, "org.kde.kwin.Scripting.start"], capture_output=True, timeout=3
        )
        time.sleep(0.3)
        return loaded.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def focus_game(window_title: str = "Satisfactory") -> bool:
    """
    Give the game real input focus. KWin scripting is the primary path (the only
    thing that actually routes keys + mouse-look to an XWayland game on this
    Wayland session); xdotool `windowactivate --sync` is a fallback for X11 /
    other compositors. `windowactivate` (not `windowfocus`) is what XWayland
    needs there — `windowfocus` leaves a different window active.
    """
    if _kwin_activate(window_title):
        time.sleep(0.2)
        return True
    result = subprocess.run(
        ["xdotool", "search", "--name", window_title, "windowactivate", "--sync"],
        capture_output=True,
        timeout=3,
    )
    time.sleep(0.2)
    return result.returncode == 0


def ensure_game_input_ready(window_title: str = "Satisfactory") -> bool:
    """
    Restore the game's keyboard input path before sending keys.

    UE5 silently drops keyboard input until the viewport regains *mouse
    capture* — which only happens on a mouse click inside the window. So a
    bare `focus_game()` isn't enough: keys like E/Tab are swallowed even
    with the window active. The fix is activate-window → centre the OS
    cursor → RIGHT-click.

    Right-click is the safe recapture primitive: unlike left-click it never
    fires the equipped weapon or places a building, so it won't hurt a tamed
    Doggo or the world while just restoring focus.

    A single click only flips capture ~50% of the time (measured live), so
    we click twice — two clicks scored best (4/6 vs 1/6 for activate-only).
    It is still not 100%, so callers must verify the resulting UI and retry
    (see collect_doggo_gift / check_inventory_full).
    """
    activated = focus_game(window_title)
    sw = cfg.get("display.screen_width", 2560)
    sh = cfg.get("display.screen_height", 1440)
    _mouse.position = (sw // 2, sh // 2)
    time.sleep(0.08)
    ui = _get_uinput_mouse()
    for _ in range(2):
        ui.write(ev_codes.EV_KEY, ev_codes.BTN_RIGHT, 1)
        ui.syn()
        time.sleep(0.05)
        ui.write(ev_codes.EV_KEY, ev_codes.BTN_RIGHT, 0)
        ui.syn()
        time.sleep(0.1)
    return activated


def press(key: str, delay_after: float = 0.05) -> None:
    code = _resolve_key_code(key)
    ui = _get_uinput_keyboard()
    ui.write(ev_codes.EV_KEY, code, 1)
    ui.syn()
    time.sleep(0.02)
    ui.write(ev_codes.EV_KEY, code, 0)
    ui.syn()
    time.sleep(delay_after)


def hold(key: str, duration: float) -> None:
    code = _resolve_key_code(key)
    ui = _get_uinput_keyboard()
    ui.write(ev_codes.EV_KEY, code, 1)
    ui.syn()
    time.sleep(duration)
    ui.write(ev_codes.EV_KEY, code, 0)
    ui.syn()


def hold_keys(keys: list[str], duration: float) -> None:
    resolved = [_resolve_key_code(k) for k in keys]
    ui = _get_uinput_keyboard()
    for code in resolved:
        ui.write(ev_codes.EV_KEY, code, 1)
    ui.syn()
    time.sleep(duration)
    for code in resolved:
        ui.write(ev_codes.EV_KEY, code, 0)
    ui.syn()


def keys_down(keys: list[str]) -> None:
    ui = _get_uinput_keyboard()
    for k in keys:
        code = _resolve_key_code(k)
        ui.write(ev_codes.EV_KEY, code, 1)
    ui.syn()


def keys_up(keys: list[str]) -> None:
    import contextlib
    ui = _get_uinput_keyboard()
    for k in keys:
        with contextlib.suppress(Exception):
            code = _resolve_key_code(k)
            ui.write(ev_codes.EV_KEY, code, 0)
    ui.syn()


def tap_key(key: str, duration: float = 0.0) -> None:
    code = _resolve_key_code(key)
    ui = _get_uinput_keyboard()
    ui.write(ev_codes.EV_KEY, code, 1)
    ui.syn()
    if duration > 0:
        time.sleep(duration)
    ui.write(ev_codes.EV_KEY, code, 0)
    ui.syn()


_OPPOSITE_KEY = {"w": "s", "s": "w", "a": "d", "d": "a"}


def opposite_keys(keys: list[str]) -> list[str]:
    return [_OPPOSITE_KEY.get(k, k) for k in keys]


def _home_cursor() -> None:
    """
    Park the in-game UI cursor at the top-left corner (0, 0).

    The game holds an XWayland pointer lock even inside menus, so the OS
    pointer is frozen — pynput/xdotool absolute warps do NOT move the
    in-game cursor (verified live: pynput reads a constant locked position).
    Only relative motion drives it. Large negative deltas saturate against
    the screen edge, giving a known origin to move from.
    """
    for _ in range(3):
        move_mouse_relative(-1500, -1500)
        time.sleep(0.12)
    time.sleep(0.15)


def _step_move(dx: int, dy: int, step: int = 2, pause: float = 0.012) -> None:
    """
    Move the cursor by a relative (dx, dy) in small slow steps.

    KWin/libinput pointer acceleration amplifies fast relative motion (~2x
    measured), so a single big delta overshoots. Small slow steps stay under
    the accel threshold and map ~1:1 to pixels. Calibrated live 2026-06-30
    against inventory-slot tooltips (targets within a few px of where the
    cursor actually landed across the whole screen).
    """
    sx = 1 if dx >= 0 else -1
    rem = abs(int(dx))
    while rem > 0:
        d = min(step, rem)
        move_mouse_relative(sx * d, 0)
        rem -= d
        time.sleep(pause)
    sy = 1 if dy >= 0 else -1
    rem = abs(int(dy))
    while rem > 0:
        d = min(step, rem)
        move_mouse_relative(0, sy * d)
        rem -= d
        time.sleep(pause)


def move_cursor_to(x: int, y: int) -> None:
    """
    Position the in-game UI cursor at absolute screen coords (x, y).

    Homes to the top-left corner then walks to the target in slow steps.
    This is the ONLY reliable way to place the menu cursor — see
    _home_cursor / _step_move for why absolute positioning is impossible.
    """
    _home_cursor()
    _step_move(x, y)
    time.sleep(0.15)


def click(x: int, y: int, button: str = "left", delay_after: float = 0.1) -> None:
    move_cursor_to(x, y)
    code = ev_codes.BTN_LEFT if button == "left" else ev_codes.BTN_RIGHT
    ui = _get_uinput_mouse()
    ui.write(ev_codes.EV_KEY, code, 1)
    ui.syn()
    time.sleep(0.03)
    ui.write(ev_codes.EV_KEY, code, 0)
    ui.syn()
    time.sleep(delay_after)


def right_click(x: int, y: int, delay_after: float = 0.1) -> None:
    click(x, y, button="right", delay_after=delay_after)


def respawn_confirm() -> None:
    sw = cfg.get("display.screen_width", 2560)
    sh = cfg.get("display.screen_height", 1440)
    _mouse.position = (sw // 2, sh // 2)
    time.sleep(0.2)
    ui = _get_uinput_mouse()
    ui.write(ev_codes.EV_KEY, ev_codes.BTN_RIGHT, 1)
    ui.syn()
    time.sleep(0.3)
    ui.write(ev_codes.EV_KEY, ev_codes.BTN_RIGHT, 0)
    ui.syn()


def shift_click(x: int, y: int, delay_after: float = 0.15) -> None:
    move_cursor_to(x, y)
    ui_kb = _get_uinput_keyboard()
    ui_m = _get_uinput_mouse()
    # Press Shift on virtual keyboard
    ui_kb.write(ev_codes.EV_KEY, ev_codes.KEY_LEFTSHIFT, 1)
    ui_kb.syn()
    time.sleep(0.02)
    # Click Left Button on virtual mouse
    ui_m.write(ev_codes.EV_KEY, ev_codes.BTN_LEFT, 1)
    ui_m.syn()
    time.sleep(0.03)
    ui_m.write(ev_codes.EV_KEY, ev_codes.BTN_LEFT, 0)
    ui_m.syn()
    # Release Shift on virtual keyboard
    ui_kb.write(ev_codes.EV_KEY, ev_codes.KEY_LEFTSHIFT, 0)
    ui_kb.syn()
    time.sleep(delay_after)


def drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.4) -> None:
    move_cursor_to(start_x, start_y)
    ui = _get_uinput_mouse()
    ui.write(ev_codes.EV_KEY, ev_codes.BTN_LEFT, 1)
    ui.syn()
    time.sleep(0.05)
    # Cursor is at (start_x, start_y); walk the relative delta to the end
    # point in slow steps so the held-button drag tracks ~1:1.
    _step_move(end_x - start_x, end_y - start_y)
    ui.write(ev_codes.EV_KEY, ev_codes.BTN_LEFT, 0)
    ui.syn()
    time.sleep(0.1)


def move_mouse_relative(dx: int, dy: int) -> None:
    ui = _get_uinput_mouse()
    ui.write(ev_codes.EV_REL, ev_codes.REL_X, dx)
    ui.write(ev_codes.EV_REL, ev_codes.REL_Y, dy)
    ui.syn()


def aim_at_screen_position(
    target_x: int,
    target_y: int,
    screen_center_x: int,
    screen_center_y: int,
    sensitivity_factor: float | None = None,
) -> None:
    factor = sensitivity_factor if sensitivity_factor is not None else cfg.get("combat.aim_sensitivity_factor", 0.8)
    dx = int((target_x - screen_center_x) * factor)
    dy = int((target_y - screen_center_y) * factor)
    move_mouse_relative(dx, dy)
    time.sleep(0.05)


def interact() -> None:
    press("e", delay_after=0.1)


def open_inventory() -> None:
    press("tab", delay_after=0.3)


def close_menu() -> None:
    # Escape is dropped unless the game window is X-active (UE5 swallows keys
    # otherwise — measured live: a bare Escape left the inventory open at
    # conf 0.999). Activate the window first so the close actually lands.
    focus_game()
    press("escape", delay_after=0.2)


def shoot(bursts: int | None = None, interval: float | None = None) -> None:
    n = bursts if bursts is not None else cfg.get("combat.shoot_bursts", 5)
    t = interval if interval is not None else cfg.get("combat.shoot_interval_seconds", 0.08)
    ui = _get_uinput_mouse()
    for _ in range(n):
        ui.write(ev_codes.EV_KEY, ev_codes.BTN_LEFT, 1)
        ui.syn()
        time.sleep(0.03)
        ui.write(ev_codes.EV_KEY, ev_codes.BTN_LEFT, 0)
        ui.syn()
        time.sleep(t)


def move_forward(duration: float) -> None:
    hold("w", duration)


def move_backward(duration: float) -> None:
    hold("s", duration)


def strafe_left(duration: float) -> None:
    hold("a", duration)


def strafe_right(duration: float) -> None:
    hold("d", duration)


def dodge(direction: str | None = None) -> None:
    dir_ = direction if direction is not None else cfg.get("combat.dodge_direction", "a")
    hold(dir_, 0.15)


def loot_remains() -> None:
    move_mouse_relative(0, 80)
    time.sleep(0.1)
    interact()
    time.sleep(0.5)
