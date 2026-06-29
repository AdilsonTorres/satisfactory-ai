"""
activities/exploration.py

Exploration activities.
"""

import logging
import time

from temporalio import activity

from utils import config as cfg
from utils import input as inp
from utils.screenshot import save_debug_screenshot

from ._shared import get_vision, screenshot_on_error

logger = logging.getLogger(__name__)


@activity.defn
async def get_exploration_route() -> dict:
    """Reads [exploration] from config.toml — config/file I/O must happen in an activity, not in workflow code (the Temporal sandbox forbids `open()` there)."""
    return {
        "route": cfg.get("exploration.route", []),
        "max_total_duration_seconds": cfg.get("exploration.max_total_duration_seconds", 25.0),
        "check_interval": cfg.get("exploration.check_interval_seconds", 1.0),
        "ascend_every": cfg.get("exploration.ascend_every_chunks", 0),
        "ascend_pulse": cfg.get("exploration.ascend_pulse_seconds", 0.3),
    }


@activity.defn
async def capture_base_reference() -> str:
    """
    Snapshots the character's current position as the 'base' reference
    point for an exploration run — assumes the player is at/near base when
    this is called (true for an AFK session). Used only as a visual record
    of the starting point; ExplorationWorkflow returns via the mirrored
    key sequence, not via image matching against this screenshot.
    """
    inp.focus_game("Satisfactory")
    time.sleep(0.2)
    path = save_debug_screenshot("base_reference")
    logger.info("Base reference captured: %s", path)
    return str(path)


@activity.defn
async def explore_leg(
    keys: list[str],
    duration: float,
    turn_dx: int = 0,
    leg_index: int = 0,
    check_interval: float = 1.0,
    ascend_every: int = 0,
    ascend_pulse: float = 0.3,
) -> dict:
    """
    Runs one leg of an exploration route: turns the camera by turn_dx,
    then holds `keys` simultaneously (ex: ["w", "space"] to advance while
    holding jump for Hover Pack ascend/glide), in `check_interval`-sized
    chunks instead of one long blind hold — checking health/death and
    saving a screenshot after EVERY chunk, stopping immediately if death
    is detected.

    Built after a live death during a single 3.5s uninterrupted 'w' hold
    on 2026-06-25: the only health/death checks were before and after
    that hold, so the cause of death couldn't be pinned down from the
    screenshots — there was no checkpoint inside the window where it
    happened. Sub-second-to-1s chunks close that gap.

    ascend_every (if >0): taps space for ascend_pulse seconds every N
    chunks, interleaved with movement, to counter altitude loss while
    flying — independent of whether 'space' is already in `keys`.

    Re-focuses the game window before every leg — input is otherwise
    silently swallowed by whatever window happens to have focus (ex: the
    terminal running this worker), which can make a whole route a no-op
    without raising any error (confirmed live on 2026-06-25: a full route
    produced identical before/after screenshots until focus was restored).
    """
    with screenshot_on_error(f"explore_leg_{leg_index}"):
        v = get_vision()
        inp.focus_game("Satisfactory")
        time.sleep(0.15)

        if turn_dx:
            inp.move_mouse_relative(turn_dx, 0)
            time.sleep(0.15)

        elapsed = 0.0
        chunk_index = 0
        died = False
        health_low = False
        screenshots: list[str] = []
        samples: list[dict] = []
        min_health = 1.0

        # Hold the movement keys down for the WHOLE leg and assess while still
        # moving, instead of press-hold-release-then-check each chunk. This
        # keeps the character in constant motion — the user's own safety model
        # ("the safe way is constant moving; the danger is stopping in a
        # hazard, losing the Hover Pack charge, and dropping"). Combined with
        # the fast region grabs (~0.6s vs the old ~7.5s full-frame capture),
        # the per-chunk pause is now negligible. try/finally guarantees the
        # keys are released even if a grab raises, so the character can't be
        # left walking off on its own.
        inp.keys_down(keys)
        try:
            while elapsed < duration:
                activity.heartbeat(f"leg {leg_index} chunk {chunk_index}")
                chunk = min(check_interval, duration - elapsed)

                # Ascend pulse: tap space WITHOUT releasing the movement keys.
                if ascend_every > 0 and chunk_index > 0 and chunk_index % ascend_every == 0:
                    inp.tap_key("space", ascend_pulse)

                time.sleep(chunk)  # character keeps moving here
                elapsed += chunk

                # assess() reads the HUD (health bar segments, damage vignette,
                # hover gauge) AND the death overlay in two small fast grabs
                # (~0.6s) and hands back the HUD crop so we save it without a
                # third grab — all while the movement keys are still held.
                status, hud = v.assess()
                path = save_debug_screenshot(f"explore_leg_{leg_index}_{chunk_index}", frame=hud)
                screenshots.append(str(path))

                health_low = status["health_low"]
                died = status["died"]
                min_health = min(min_health, status["health_frac"])
                samples.append(
                    {
                        "chunk": chunk_index,
                        "elapsed": round(elapsed, 2),
                        "health_frac": status["health_frac"],
                        "health_segments": status["health_segments"],
                        "damage_red": round(status["damage_red"], 4),
                        "gauge_frac": status["gauge_frac"],
                        "died": died,
                    }
                )

                logger.info(
                    "Leg %d chunk %d: keys=%s elapsed=%.1f/%.1fs turn_dx=%d hp=%d/10 dmg_red=%.3f gauge=%s died=%s",
                    leg_index,
                    chunk_index,
                    keys,
                    elapsed,
                    duration,
                    turn_dx,
                    status["health_segments"],
                    status["damage_red"],
                    status["gauge_frac"],
                    died,
                )
                chunk_index += 1
                activity.heartbeat(f"leg {leg_index} chunk {chunk_index} done")

                if died:
                    logger.warning("Death detected mid-leg (chunk %d) — stopping this leg immediately.", chunk_index)
                    break
                # Stop moving deeper into a hazard the moment health is low —
                # the workflow will retrace from here rather than push on.
                if health_low:
                    logger.warning(
                        "Low health mid-leg (chunk %d, %d/10) — stopping this leg.",
                        chunk_index,
                        status["health_segments"],
                    )
                    break
        finally:
            inp.keys_up(keys)

        return {
            "keys": keys,
            "duration": elapsed,
            "turn_dx": turn_dx,
            "health_low": health_low,
            "died": died,
            "min_health_frac": min_health,
            "screenshots": screenshots,
            "samples": samples,
        }


@activity.defn
async def return_via_reverse_route(legs_taken: list[dict]) -> bool:
    """
    Retraces legs_taken in reverse order with mirrored keys (w<->s, a<->d;
    'space' passes through unchanged) and mirrored turns, to head back
    toward the start of an exploration run. Same blind-navigation idiom as
    navigate_back_to_base — approximate, not vision-verified.
    """
    with screenshot_on_error("return_via_reverse_route"):
        inp.focus_game("Satisfactory")
        time.sleep(0.2)
        logger.info("Returning via %d reversed leg(s)...", len(legs_taken))
        for i, leg in enumerate(reversed(legs_taken)):
            activity.heartbeat(f"return step {i + 1}/{len(legs_taken)}")
            reversed_keys = inp.opposite_keys(leg["keys"])
            inp.hold_keys(reversed_keys, leg["duration"])
            if leg["turn_dx"]:
                inp.move_mouse_relative(-leg["turn_dx"], 0)
                time.sleep(0.15)

        path = save_debug_screenshot("back_at_base")
        logger.info("Return sequence complete. Screenshot: %s", path)
        return True
