"""
utils/input.py
Envia inputs de mouse/teclado para o Satisfactory via pydirectinput.
pydirectinput usa DirectInput — funciona em jogos 3D sem anti-cheat.
"""
import time
import pydirectinput
import pygetwindow as gw

pydirectinput.PAUSE = 0.0


def focus_game(window_title: str = "Satisfactory") -> bool:
    """Traz o jogo para o foco antes de enviar inputs."""
    windows = gw.getWindowsWithTitle(window_title)
    if not windows:
        return False
    windows[0].activate()
    time.sleep(0.2)
    return True


def press(key: str, delay_after: float = 0.05):
    pydirectinput.press(key)
    time.sleep(delay_after)


def hold(key: str, duration: float):
    pydirectinput.keyDown(key)
    time.sleep(duration)
    pydirectinput.keyUp(key)


def click(x: int, y: int, button: str = "left", delay_after: float = 0.1):
    pydirectinput.moveTo(x, y)
    time.sleep(0.05)
    pydirectinput.click(x, y, button=button)
    time.sleep(delay_after)


def right_click(x: int, y: int, delay_after: float = 0.1):
    click(x, y, button="right", delay_after=delay_after)


def move_mouse_relative(dx: int, dy: int):
    """Move o mouse de forma relativa — essencial para câmera 3D (Raw Input)."""
    pydirectinput.move(dx, dy, relative=True)


def aim_at_screen_position(
    target_x: int,
    target_y: int,
    screen_center_x: int,
    screen_center_y: int,
    sensitivity_factor: float = 1.0,
):
    """
    Move a mira para um ponto na tela.
    sensitivity_factor: calibre empiricamente (comece em 1.0 e ajuste).
    """
    dx = int((target_x - screen_center_x) * sensitivity_factor)
    dy = int((target_y - screen_center_y) * sensitivity_factor)
    move_mouse_relative(dx, dy)
    time.sleep(0.05)


def interact():
    press("e", delay_after=0.1)


def open_inventory():
    press("tab", delay_after=0.3)


def close_menu():
    press("escape", delay_after=0.2)


def shoot(bursts: int = 3, interval: float = 0.1):
    for _ in range(bursts):
        pydirectinput.click(button="left")
        time.sleep(interval)


def move_forward(duration: float):
    hold("w", duration)


def move_backward(duration: float):
    hold("s", duration)


def strafe_left(duration: float):
    hold("a", duration)


def strafe_right(duration: float):
    hold("d", duration)


def dodge(direction: str = "a"):
    hold(direction, 0.15)


def loot_remains():
    """
    Olha levemente para baixo (remains ficam no chão) e interage.
    """
    move_mouse_relative(0, 80)
    time.sleep(0.1)
    interact()
    time.sleep(0.5)
