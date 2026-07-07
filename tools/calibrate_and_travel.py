"""
tools/calibrate_and_travel.py

Automatically calibrates camera turn sensitivity in degrees-per-pixel,
faces the nearest main power grid pole, walks the character in range,
and triggers sbot map to generate the powered routes.
"""

import math
import sys
import time
from pathlib import Path

import numpy as np

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tools.cli import _find_latest_save_file  # noqa: E402
from utils.input import hold_keys, move_mouse_relative, press  # noqa: E402
from utils.save_parser import SatisfactorySave  # noqa: E402


def get_player_state():
    save_path = _find_latest_save_file()
    if not save_path:
        raise RuntimeError("No save file found.")

    save = SatisfactorySave(save_path)
    if not save.players:
        raise RuntimeError("No player found in save.")

    player = save.players[0]
    pos = np.array(player["position"])

    char_path = player["character_path"]
    char_obj = save.levels_objects[char_path]
    rot = char_obj["rotation"]

    # Convert quaternion to yaw
    qx, qy, qz, qw = rot
    siny_cosp = 2 * (qw * qz + qx * qy)
    cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
    yaw = math.degrees(math.atan2(siny_cosp, cosy_cosp))

    return pos, yaw, save_path


def focus_game():
    import subprocess
    print("Searching for game window to focus...")
    for pattern in ["Satisfactory", "FactoryGame"]:
        try:
            res = subprocess.check_output(["xdotool", "search", "--onlyvisible", "--name", pattern]).decode().strip()
            if res:
                win_id = res.split()[0]
                print(f"Found game window ID: {win_id}. Focusing it...")
                subprocess.call(["xdotool", "windowactivate", "--sync", win_id])
                time.sleep(1.0)
                return True
        except Exception as e:
            print(f"Window search failed for pattern '{pattern}': {e}")
    print("Warning: Could not find or focus Satisfactory window. Continuing anyway...")
    return False


def trigger_quicksave():
    print("Sending Quicksave command (F5)...")
    press("f5")
    print("Waiting 5 seconds for save to write to disk...")
    time.sleep(5.0)


def calibrate_and_travel():
    # 0. Focus game
    focus_game()

    # 1. Capture initial state
    trigger_quicksave()
    pos, yaw, save_file = get_player_state()
    print(f"Initial State: Pos={pos}, Yaw={yaw:.2f}°, Save={Path(save_file).name}")

    # Nearest main power pole target coordinate
    target_pos = np.array([-16450.0, -116350.0, 10000.0])
    dist = np.linalg.norm(target_pos - pos)
    print(f"Nearest main power pole is {dist/100.0:.2f} meters away.")

    if dist <= 2800.0:
        print("Already in range of the main power grid (distance <= 28 meters).")
        return

    # 2. Make a calibration turn of 600 pixels to the right
    test_turn_pixels = 600
    print(f"Making calibration turn of {test_turn_pixels} pixels to the right...")
    move_mouse_relative(test_turn_pixels, 0)
    time.sleep(1.0)

    trigger_quicksave()
    new_pos, new_yaw, new_save_file = get_player_state()
    print(f"Post-calibration State: Yaw={new_yaw:.2f}°, Save={Path(new_save_file).name}")

    # Calculate degrees per pixel
    yaw_diff = new_yaw - yaw
    # Handle angle wrap-around
    if yaw_diff > 180:
        yaw_diff -= 360
    elif yaw_diff < -180:
        yaw_diff += 360

    if abs(yaw_diff) < 2.0:
        print("Error: Calibration turn did not result in a yaw change. Is the game focused?")
        return

    pixels_per_degree = test_turn_pixels / yaw_diff
    print(f"Calibrated Turn Sensitivity: {pixels_per_degree:.2f} pixels/degree.")

    # 3. Calculate target yaw to face the pole from the CURRENT position and yaw
    dx = target_pos[0] - new_pos[0]
    dy = target_pos[1] - new_pos[1]
    target_yaw = math.degrees(math.atan2(dy, dx))

    turn_angle = target_yaw - new_yaw
    if turn_angle > 180:
        turn_angle -= 360
    elif turn_angle < -180:
        turn_angle += 360

    # Calculate remaining pixels to turn to face target exactly
    final_turn_pixels = int(turn_angle * pixels_per_degree)
    print(f"Target Yaw: {target_yaw:.2f}°. Remaining turn angle: {turn_angle:.2f}°. Turning {final_turn_pixels} pixels...")
    move_mouse_relative(final_turn_pixels, 0)
    time.sleep(1.0)

    # 4. Walk forward to reach the pole
    # Run speed is ~9.0 m/s (900 cm/s). Let's walk for (dist - 1500) / 900 seconds
    walk_dist = dist - 1500.0  # leave 15m buffer inside the 30m range
    walk_duration = max(1.0, walk_dist / 900.0)
    print(f"Walking forward towards main grid for {walk_duration:.1f} seconds...")

    # Hold W for duration
    hold_keys(["w"], walk_duration)
    time.sleep(1.0)

    # 5. Save and verify new position
    trigger_quicksave()
    final_pos, final_yaw, final_save_file = get_player_state()
    final_dist = np.linalg.norm(target_pos - final_pos)
    print(f"Final State: Pos={final_pos}, Yaw={final_yaw:.2f}°, Save={Path(final_save_file).name}")
    print(f"Final distance to main power pole: {final_dist/100.0:.1f} meters.")

    if final_dist <= 3000.0:
        print("Success! You are now powered by the main grid!")
    else:
        print("Walking complete, but still outside 30m. Try running this travel script again.")


if __name__ == "__main__":
    calibrate_and_travel()
