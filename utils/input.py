"""
utils/input.py
Envia inputs de mouse/teclado para o Satisfactory via pydirectinput.
Sensitividade e outros parâmetros veem de config.toml.
"""
import time
import pydirectinput
import pygetwindow as gw

from utils import config as cfg

pydirectinput.PAUSE = 0.0


def focus_game(window_title: str = "Satisfactory") -> bool:
    windows = gw.getWindowsWithTitle(window_title)
    if not windows:
        return False
    windows[0].activate()
    time.sleep(0.2)
    return True


def press(key: str, delay_after: float = 0.05) -> None:
    pydirectinput.press(key)
    time.sleep(delay_after)


def hold(key: str, duration: float) -> None:
    pydirectinput.keyDown(key)
    time.sleep(duration)
    pydirectinput.keyUp(key)


def click(x: int, y: int, button: str = "left", delay_after: float = 0.1) -> None:
    pydirectinput.moveTo(x, y)
    time.sleep(0.05)
    pydirectinput.click(x, y, button=button)
    time.sleep(delay_after)


def right_click(x: int, y: int, delay_after: float = 0.1) -> None:
    click(x, y, button="right", delay_after=delay_after)


def move_mouse_relative(dx: int, dy: int) -> None:
    """Movimento relativo via Raw Input — funciona em jogos 3D."""
    pydirectinput.move(dx, dy, relative=True)


def aim_at_screen_position(
    target_x: int,
    target_y: int,
    screen_center_x: int,
    screen_center_y: int,
    sensitivity_factor: Optional[float] = None,
) -> None:
    """
    Move a mira para (target_x, target_y).
    sensitivity_factor: se None, usa config.toml[combat.aim_sensitivity_factor].
    """
    factor = sensitivity_factor if sensitivity_factor is not None else cfg.get(
        "combat.aim_sensitivity_factor", 0.8
    )
    dx = int((target_x - screen_center_x) * factor)
    dy = int((target_y - screen_center_y) * factor)
    move_mouse_relative(dx, dy)
    time.sleep(0.05)


# Atalho para evitar import circular com typing
from typing import Optional  # noqa: E402 — mantido ao final por dependência de aim_at_screen_position


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
        pydirectinput.click(button="left")
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
