"""Safety controls with fully fake devices: never connect to a desktop/uinput."""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def safe_input(monkeypatch):
    codes = types.SimpleNamespace(
        **{
            name: index
            for index, name in enumerate(
                [
                    "EV_REL",
                    "REL_X",
                    "REL_Y",
                    "REL_WHEEL",
                    "EV_KEY",
                    "BTN_LEFT",
                    "BTN_RIGHT",
                    "KEY_ESC",
                    "KEY_TAB",
                    "KEY_ENTER",
                    "KEY_SPACE",
                    "KEY_LEFTSHIFT",
                    "KEY_LEFTCTRL",
                    "KEY_LEFTALT",
                    "KEY_W",
                    "KEY_A",
                    "KEY_S",
                    "KEY_D",
                    "KEY_E",
                    "KEY_F",
                    "KEY_R",
                    "KEY_Q",
                ]
            )
        }
    )
    evdev = types.ModuleType("evdev")
    evdev.ecodes = codes
    evdev.UInput = MagicMock(side_effect=AssertionError("real input devices forbidden"))
    config = types.SimpleNamespace(get=lambda _key, default=None: default)
    utils = types.ModuleType("utils")
    utils.config = config
    pynput = types.ModuleType("pynput")
    mouse_backend = types.ModuleType("pynput.mouse")
    mouse_backend.Button = types.SimpleNamespace(right="right")
    for name, module in {"evdev": evdev, "utils": utils, "pynput": pynput, "pynput.mouse": mouse_backend}.items():
        monkeypatch.setitem(sys.modules, name, module)
    source = Path(__file__).resolve().parents[1] / "utils/input.py"
    spec = importlib.util.spec_from_file_location("sat_input_safety_fixture", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    mouse = MagicMock()
    monkeypatch.setattr(module, "_get_mouse", MagicMock(return_value=mouse))
    monkeypatch.setattr(module, "_active_window_name", lambda: "Satisfactory")
    return module, mouse


def test_failed_focus_aborts_before_accessing_mouse(safe_input, monkeypatch):
    module, mouse = safe_input
    monkeypatch.setattr(module, "focus_game", lambda _title: False)
    with pytest.raises(RuntimeError, match="focus"):
        module.ensure_game_input_ready()
    module._get_mouse.assert_not_called()
    mouse.press.assert_not_called()
    mouse.release.assert_not_called()


def test_interrupted_click_releases_before_propagating(safe_input, monkeypatch):
    module, mouse = safe_input
    monkeypatch.setattr(module, "focus_game", lambda _title: True)

    def interrupt(seconds):
        if seconds == 0.05:
            raise RuntimeError("synthetic interruption while pressed")

    monkeypatch.setattr(module.time, "sleep", interrupt)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        module.ensure_game_input_ready()
    mouse.press.assert_called_once_with("right")
    mouse.release.assert_called_once_with("right")


def test_lost_focus_before_click_emits_no_button_event(safe_input, monkeypatch):
    module, mouse = safe_input
    monkeypatch.setattr(module, "focus_game", lambda _title: True)
    monkeypatch.setattr(module, "_active_window_name", lambda: "Unrelated application")
    with pytest.raises(RuntimeError, match="focus"):
        module.ensure_game_input_ready()
    mouse.press.assert_not_called()


def test_verified_focus_pairs_both_clicks(safe_input, monkeypatch):
    module, mouse = safe_input
    monkeypatch.setattr(module, "focus_game", lambda _title: True)
    assert module.ensure_game_input_ready() is True
    assert mouse.press.call_count == mouse.release.call_count == 2
    assert mouse.position == (1280, 720)


def test_focus_loss_after_first_click_prevents_second(safe_input, monkeypatch):
    module, mouse = safe_input
    monkeypatch.setattr(module, "focus_game", lambda _title: True)
    titles = iter(["Satisfactory", "Satisfactory", "Unrelated application"])
    monkeypatch.setattr(module, "_active_window_name", lambda: next(titles))
    with pytest.raises(module.FocusNotReadyError, match="focus"):
        module.ensure_game_input_ready()
    mouse.press.assert_called_once_with("right")
    mouse.release.assert_called_once_with("right")
