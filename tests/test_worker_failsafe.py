from unittest.mock import MagicMock
from workers.worker import _is_fail_safe_key


def test_is_fail_safe_key():
    try:
        from pynput import keyboard
    except ImportError:
        # Skip if pynput is not available in the running environment
        return

    # Test F12 matches
    assert _is_fail_safe_key(keyboard.Key.f12, "F12")
    assert _is_fail_safe_key(keyboard.Key.f12, "  f12  ")
    assert not _is_fail_safe_key(keyboard.Key.f11, "F12")

    # Test ESC / escape matches
    assert _is_fail_safe_key(keyboard.Key.esc, "esc")
    assert _is_fail_safe_key(keyboard.Key.esc, "escape")
    assert _is_fail_safe_key(keyboard.Key.esc, "Key.esc")

    # Test character matching
    char_key = MagicMock()
    char_key.char = "q"
    assert _is_fail_safe_key(char_key, "q")
    assert _is_fail_safe_key(char_key, "Q")
    assert not _is_fail_safe_key(char_key, "F12")
