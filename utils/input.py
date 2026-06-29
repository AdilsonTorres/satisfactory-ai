"""
utils/input.py
Sends mouse/keyboard input to Satisfactory on Linux.
Uses separate virtual mouse and virtual keyboard devices via uinput (evdev)
to bypass Proton and Wayland security filters.
X11 (pynput) is still used only to query and move the desktop cursor position absolutely.
"""

import atexit
import subprocess
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


def focus_game(window_title: str = "Satisfactory") -> bool:
    result = subprocess.run(
        ["xdotool", "search", "--name", window_title, "windowfocus", "--sync"],
        capture_output=True,
        timeout=3,
    )
    time.sleep(0.2)
    return result.returncode == 0


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


def click(x: int, y: int, button: str = "left", delay_after: float = 0.1) -> None:
    _mouse.position = (x, y)
    time.sleep(0.05)
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
    _mouse.position = (x, y)
    time.sleep(0.05)
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
    _mouse.position = (start_x, start_y)
    time.sleep(0.05)
    ui = _get_uinput_mouse()
    ui.write(ev_codes.EV_KEY, ev_codes.BTN_LEFT, 1)
    ui.syn()
    steps = max(int(duration / 0.02), 1)
    for i in range(1, steps + 1):
        t = i / steps
        _mouse.position = (
            int(start_x + (end_x - start_x) * t),
            int(start_y + (end_y - start_y) * t),
        )
        time.sleep(duration / steps)
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
