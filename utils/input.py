"""
utils/input.py
Sends mouse/keyboard input to Satisfactory on Linux.
Uses pynput (X11/Xwayland) + xdotool for window focus, and a virtual
mouse via uinput (evdev) for relative camera movement (mouse-look).
"""
import atexit
import time
import subprocess
from typing import Optional

from evdev import UInput, ecodes as ev_codes
from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Controller as MouseController, Button

from utils import config as cfg

_kb = KeyboardController()
_mouse = MouseController()
_uinput_mouse: Optional[UInput] = None


def _get_uinput_mouse() -> UInput:
    """
    Virtual mouse device via uinput — needed because the game runs via
    Proton/Wine and ignores synthetic relative motion injected through
    X11/XTest (pynput). The kernel already exposes /dev/uinput with a
    uaccess ACL for the local session (via existing KDE Connect/Steam
    Input udev rules), so no extra rule is needed.
    """
    global _uinput_mouse
    if _uinput_mouse is None:
        capabilities = {
            ev_codes.EV_REL: [ev_codes.REL_X, ev_codes.REL_Y, ev_codes.REL_WHEEL],
        }
        _uinput_mouse = UInput(capabilities, name="satisfactory-bot-mouse")
        atexit.register(_uinput_mouse.close)
        time.sleep(0.3)  # give the compositor time to recognize the new device
    return _uinput_mouse

# Key-name to pynput map
_KEY_MAP: dict[str, Key | str] = {
    "escape": Key.esc,
    "tab": Key.tab,
    "enter": Key.enter,
    "space": Key.space,
    "shift": Key.shift,
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "w": "w", "a": "a", "s": "s", "d": "d",
    "e": "e", "f": "f", "r": "r", "q": "q",
}


def _resolve_key(key: str):
    return _KEY_MAP.get(key.lower(), key)


def focus_game(window_title: str = "Satisfactory") -> bool:
    result = subprocess.run(
        ["xdotool", "search", "--name", window_title, "windowfocus", "--sync"],
        capture_output=True,
        timeout=3,
    )
    time.sleep(0.2)
    return result.returncode == 0


def press(key: str, delay_after: float = 0.05) -> None:
    k = _resolve_key(key)
    _kb.press(k)
    time.sleep(0.02)
    _kb.release(k)
    time.sleep(delay_after)


def hold(key: str, duration: float) -> None:
    k = _resolve_key(key)
    _kb.press(k)
    time.sleep(duration)
    _kb.release(k)


def click(x: int, y: int, button: str = "left", delay_after: float = 0.1) -> None:
    btn = Button.left if button == "left" else Button.right
    _mouse.position = (x, y)
    time.sleep(0.05)
    _mouse.click(btn)
    time.sleep(delay_after)


def right_click(x: int, y: int, delay_after: float = 0.1) -> None:
    click(x, y, button="right", delay_after=delay_after)


def shift_click(x: int, y: int, delay_after: float = 0.15) -> None:
    """Shift+click — quick transfer of a slot between inventory panels (ex: to storage)."""
    _mouse.position = (x, y)
    time.sleep(0.05)
    _kb.press(Key.shift)
    _mouse.click(Button.left)
    _kb.release(Key.shift)
    time.sleep(delay_after)


def drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.4) -> None:
    """Drags with the left button held — used to take an item out of the inventory and drop it in the world."""
    _mouse.position = (start_x, start_y)
    time.sleep(0.05)
    _mouse.press(Button.left)
    steps = max(int(duration / 0.02), 1)
    for i in range(1, steps + 1):
        t = i / steps
        _mouse.position = (
            int(start_x + (end_x - start_x) * t),
            int(start_y + (end_y - start_y) * t),
        )
        time.sleep(duration / steps)
    _mouse.release(Button.left)
    time.sleep(0.1)


def move_mouse_relative(dx: int, dy: int) -> None:
    """
    Relative motion via the uinput virtual mouse — the only approach that
    rotates the first-person camera in-game (Proton/Wine ignores synthetic
    relative motion via X11/XTest/pynput).
    """
    ui = _get_uinput_mouse()
    ui.write(ev_codes.EV_REL, ev_codes.REL_X, dx)
    ui.write(ev_codes.EV_REL, ev_codes.REL_Y, dy)
    ui.syn()


def aim_at_screen_position(
    target_x: int,
    target_y: int,
    screen_center_x: int,
    screen_center_y: int,
    sensitivity_factor: Optional[float] = None,
) -> None:
    factor = sensitivity_factor if sensitivity_factor is not None else cfg.get(
        "combat.aim_sensitivity_factor", 0.8
    )
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


def shoot(bursts: Optional[int] = None, interval: Optional[float] = None) -> None:
    n = bursts if bursts is not None else cfg.get("combat.shoot_bursts", 5)
    t = interval if interval is not None else cfg.get("combat.shoot_interval_seconds", 0.08)
    for _ in range(n):
        _mouse.press(Button.left)
        time.sleep(0.03)
        _mouse.release(Button.left)
        time.sleep(t)


def move_forward(duration: float) -> None:
    hold("w", duration)


def move_backward(duration: float) -> None:
    hold("s", duration)


def strafe_left(duration: float) -> None:
    hold("a", duration)


def strafe_right(duration: float) -> None:
    hold("d", duration)


def dodge(direction: Optional[str] = None) -> None:
    dir_ = direction if direction is not None else cfg.get("combat.dodge_direction", "a")
    hold(dir_, 0.15)


def loot_remains() -> None:
    move_mouse_relative(0, 80)
    time.sleep(0.1)
    interact()
    time.sleep(0.5)
