"""
utils/input.py
Envia inputs de mouse/teclado para o Satisfactory no Linux.
Usa pynput (X11/Xwayland) + xdotool para foco de janela.
"""
import time
import subprocess
from typing import Optional

from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Controller as MouseController, Button

from utils import config as cfg

_kb = KeyboardController()
_mouse = MouseController()

# Mapa de nomes de tecla para pynput
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
    """Shift+click — transferência rápida de um slot entre painéis de inventário (ex: para storage)."""
    _mouse.position = (x, y)
    time.sleep(0.05)
    _kb.press(Key.shift)
    _mouse.click(Button.left)
    _kb.release(Key.shift)
    time.sleep(delay_after)


def drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.4) -> None:
    """Arrasta com o botão esquerdo pressionado — usado para tirar um item do inventário e soltar no mundo."""
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
    """Movimento relativo — funciona com jogos 3D no Xwayland."""
    _mouse.move(dx, dy)


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
