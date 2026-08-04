from unittest.mock import MagicMock, mock_open, patch

import pytest

import utils.input as input_module


@pytest.fixture
def mock_cfg():
    with patch("utils.input.cfg.get") as mock_get:
        mock_get.return_value = 0.5
        yield mock_get


@pytest.fixture
def mock_sleep():
    with patch("utils.input.time.sleep") as mock:
        yield mock


@pytest.fixture
def mock_uinput():
    with patch("utils.input.UInput") as mock_ui_cls:
        mock_ui = MagicMock()
        mock_ui_cls.return_value = mock_ui
        # reset module globals to ensure lazy init creates new mocks
        input_module._uinput_mouse = None
        input_module._uinput_keyboard = None
        yield mock_ui


@pytest.fixture
def mock_mouse():
    with patch("utils.input._get_mouse") as mock_get_mouse:
        mock_controller = MagicMock()
        mock_get_mouse.return_value = mock_controller
        yield mock_controller


def test_resolve_key_code() -> None:
    assert input_module._resolve_key_code("escape") == input_module.ev_codes.KEY_ESC
    assert input_module._resolve_key_code("enter") == input_module.ev_codes.KEY_ENTER
    assert input_module._resolve_key_code("shift") == input_module.ev_codes.KEY_LEFTSHIFT
    assert input_module._resolve_key_code("w") == input_module.ev_codes.KEY_W
    assert input_module._resolve_key_code("Z") == input_module.ev_codes.KEY_Z
    with pytest.raises(ValueError):
        input_module._resolve_key_code("unknown_key")


def test_qdbus_bin() -> None:
    with patch("utils.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert input_module._qdbus_bin() in ("qdbus6", "qdbus")

        mock_run.return_value = MagicMock(returncode=1)
        assert input_module._qdbus_bin() is None


def test_kwin_activate() -> None:
    with (
        patch("utils.input._qdbus_bin", return_value="qdbus"),
        patch("utils.input.tempfile.mkstemp", return_value=(1, "/tmp/kwin.js")),
        patch("utils.input.os.fdopen", mock_open()),
        patch("utils.input.os.path.exists", return_value=False),
        patch("utils.input.subprocess.run") as mock_run,
        patch("utils.input.time.sleep"),
    ):
        mock_run.return_value = MagicMock(returncode=0)
        assert input_module._kwin_activate("Satisfactory") is True


def test_active_window_name() -> None:
    with patch("utils.input.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Satisfactory\n")
        assert input_module._active_window_name() == "Satisfactory"

        mock_run.side_effect = OSError("error")
        assert input_module._active_window_name() == ""


def test_focus_game(mock_sleep) -> None:
    with (
        patch("utils.input._kwin_activate", return_value=True),
        patch("utils.input._active_window_name", return_value="Satisfactory"),
    ):
        assert input_module.focus_game() is True

    with (
        patch("utils.input._kwin_activate", return_value=False),
        patch("utils.input.subprocess.run") as mock_run,
        patch("utils.input._active_window_name", return_value=""),
    ):
        assert input_module.focus_game(retries=1) is False
        mock_run.assert_called()


def test_ensure_game_input_ready(mock_sleep, mock_mouse, mock_cfg) -> None:
    with patch("utils.input.focus_game", return_value=True):
        assert input_module.ensure_game_input_ready() is True
        mock_mouse.press.assert_called()
        mock_mouse.release.assert_called()


def test_press(mock_uinput, mock_sleep) -> None:
    input_module.press("e")
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.KEY_E, 1)
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.KEY_E, 0)
    assert mock_uinput.syn.call_count >= 2


def test_hold(mock_uinput, mock_sleep) -> None:
    input_module.hold("w", 1.0)
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.KEY_W, 1)
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.KEY_W, 0)


def test_hold_keys(mock_uinput, mock_sleep) -> None:
    input_module.hold_keys(["w", "shift"], 1.0)
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.KEY_W, 1)
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.KEY_LEFTSHIFT, 1)


def test_keys_down_up(mock_uinput, mock_sleep) -> None:
    input_module.keys_down(["a"])
    mock_uinput.write.assert_called_with(input_module.ev_codes.EV_KEY, input_module.ev_codes.KEY_A, 1)

    input_module.keys_up(["a"])
    mock_uinput.write.assert_called_with(input_module.ev_codes.EV_KEY, input_module.ev_codes.KEY_A, 0)


def test_tap_key(mock_uinput, mock_sleep) -> None:
    input_module.tap_key("space", 0.1)
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.KEY_SPACE, 1)
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.KEY_SPACE, 0)


def test_opposite_keys() -> None:
    assert input_module.opposite_keys(["w", "a"]) == ["s", "d"]
    assert input_module.opposite_keys(["space"]) == ["space"]


def test_move_mouse_relative(mock_uinput) -> None:
    input_module.move_mouse_relative(10, -20)
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_REL, input_module.ev_codes.REL_X, 10)
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_REL, input_module.ev_codes.REL_Y, -20)
    mock_uinput.syn.assert_called()


def test_home_cursor(mock_uinput, mock_sleep) -> None:
    with patch("utils.input.move_mouse_relative") as mock_rel:
        input_module._home_cursor()
        mock_rel.assert_called_with(-2800, -2800)


def test_step_move(mock_uinput, mock_sleep, mock_cfg) -> None:
    with patch("utils.input.move_mouse_relative") as mock_rel:
        input_module._step_move(5, 5, step=2, pause=0.01)
        assert mock_rel.call_count == 3  # 2, 2, 1


def test_move_cursor_to(mock_uinput, mock_sleep) -> None:
    with patch("utils.input._home_cursor") as mock_home, patch("utils.input._step_move") as mock_step:
        input_module.move_cursor_to(100, 200)
        mock_home.assert_called_once()
        mock_step.assert_called_with(100, 200)


def test_click(mock_uinput, mock_sleep) -> None:
    with patch("utils.input.move_cursor_to") as mock_move:
        input_module.click(10, 20, "left")
        mock_move.assert_called_with(10, 20)
        mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.BTN_LEFT, 1)


def test_right_click(mock_uinput, mock_sleep) -> None:
    with patch("utils.input.click") as mock_click:
        input_module.right_click(10, 20)
        mock_click.assert_called_with(10, 20, button="right", delay_after=0.1)


def test_respawn_confirm(mock_mouse, mock_sleep, mock_cfg) -> None:
    input_module.respawn_confirm()
    mock_mouse.press.assert_called()
    mock_mouse.release.assert_called()


def test_shift_click_here(mock_uinput, mock_sleep) -> None:
    input_module.shift_click_here()
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.KEY_LEFTSHIFT, 1)
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.BTN_LEFT, 1)
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.BTN_LEFT, 0)
    mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.KEY_LEFTSHIFT, 0)


def test_shift_click(mock_uinput, mock_sleep) -> None:
    with patch("utils.input.move_cursor_to") as mock_move, patch("utils.input.shift_click_here") as mock_shift:
        input_module.shift_click(10, 20)
        mock_move.assert_called_with(10, 20)
        mock_shift.assert_called_once()


def test_drag(mock_uinput, mock_sleep) -> None:
    with patch("utils.input.move_cursor_to") as mock_move, patch("utils.input._step_move") as mock_step:
        input_module.drag(10, 10, 20, 20)
        mock_move.assert_called_with(10, 10)
        mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.BTN_LEFT, 1)
        mock_step.assert_called_with(10, 10)
        mock_uinput.write.assert_any_call(input_module.ev_codes.EV_KEY, input_module.ev_codes.BTN_LEFT, 0)


def test_aim_at_screen_position(mock_uinput, mock_sleep, mock_cfg) -> None:
    with patch("utils.input.move_mouse_relative") as mock_rel:
        input_module.aim_at_screen_position(100, 100, 50, 50, sensitivity_factor=1.0)
        mock_rel.assert_called_with(50, 50)


def test_actions(mock_uinput, mock_sleep, mock_cfg) -> None:
    with (
        patch("utils.input.press") as mock_press,
        patch("utils.input.hold") as mock_hold,
        patch("utils.input.focus_game") as mock_focus,
    ):
        input_module.interact()
        mock_press.assert_called_with("e", delay_after=0.1)

        input_module.open_inventory()
        mock_press.assert_called_with("tab", delay_after=0.3)

        input_module.close_menu()
        mock_focus.assert_called()
        mock_press.assert_called_with("escape", delay_after=0.2)

        input_module.move_forward(1.0)
        mock_hold.assert_called_with("w", 1.0)

        input_module.move_backward(1.0)
        mock_hold.assert_called_with("s", 1.0)

        input_module.strafe_left(1.0)
        mock_hold.assert_called_with("a", 1.0)

        input_module.strafe_right(1.0)
        mock_hold.assert_called_with("d", 1.0)

        mock_cfg.return_value = "a"
        input_module.dodge()
        mock_hold.assert_called_with("a", 0.15)


def test_shoot(mock_uinput, mock_sleep, mock_cfg) -> None:
    input_module.shoot(bursts=2, interval=0.1)
    assert mock_uinput.write.call_count >= 4


def test_loot_remains(mock_uinput, mock_sleep) -> None:
    with patch("utils.input.move_mouse_relative") as mock_rel, patch("utils.input.interact") as mock_int:
        input_module.loot_remains()
        mock_rel.assert_called_with(0, 80)
        mock_int.assert_called_once()
