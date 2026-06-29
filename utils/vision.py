"""
utils/vision.py
Screen capture and visual detection via template matching.
Thresholds are read automatically from config.toml per template.
"""

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import mss
import mss.exception
import numpy as np

from utils import config as cfg

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Health bar geometry at 2560x1440, measured live 2026-06-25 from the
# bottom-left HUD region grabbed at offset (0, 1230): 10 fixed segment boxes
# to the right of the heart icon. Full health = all 10 bright; the bar
# depletes right-to-left (rightmost segments go dark first). Coordinates are
# relative to that (0,1230) grab. Recalibrate if display/game resolution or
# the HUD scale changes.
_HEALTH_REGION = (0, 1230, 760, 200)  # x, y, w, h (full-frame coords)
_HEALTH_BAR_Y = (88, 132)  # segment row, local to the grab
_HEALTH_SEGMENTS = [  # (x0, x1) of each segment, local
    (134, 163),
    (168, 197),
    (202, 231),
    (236, 265),
    (271, 299),
    (305, 334),
    (339, 368),
    (373, 402),
    (408, 437),
    (442, 470),
]
_HEALTH_BRIGHT_V = 140  # HSV V above which a pixel is "lit"
_HEALTH_SEGMENT_LIT_FRAC = 0.30  # a segment counts as full if >30% lit

# 'Press RMB to Respawn' overlay lives center-screen; grab a band slightly
# larger than the death_screen template so matchTemplate has room to slide.
_DEATH_REGION = (1040, 760, 470, 130)  # x, y, w, h (full-frame coords)

# Hover Pack charge gauge: a spinning orange three-blade fan inside a thin
# WHITE ring, bottom-left (above the health bar). The ring only renders while
# flying; the white depletes as the player leaves electric-pole range. Charge
# fraction = portion of the ring still white. Calibrated live on 2026-06-25
# (HoughCircles + a full-ring best-fit search) at 2560x1440 -> center (190,1172),
# ring radius 38. The orange fan (inner disk) flags "gauge visible / flying".
_GAUGE_CENTER = (190, 1172)  # full-frame ring center (x, y)
_GAUGE_RADIUS = 38  # white-ring radius (px)
_GAUGE_REGION = (135, 1117, 110, 110)  # x, y, w, h grab around the ring
_GAUGE_RING_VBRIGHT = 140  # V above which a ring pixel is "white"
_GAUGE_RING_SMAX = 90  # S below which it's white (not orange)


@dataclass
class MatchResult:
    found: bool
    x: int = 0
    y: int = 0
    confidence: float = 0.0
    template_name: str = ""

    @property
    def center(self) -> tuple[int, int]:
        return self.x, self.y

    def __str__(self) -> str:
        if self.found:
            return f"MatchResult(found=True, pos=({self.x},{self.y}), conf={self.confidence:.3f})"
        return f"MatchResult(found=False, best_conf={self.confidence:.3f})"


class Vision:
    """
    Local computer-vision wrapper.
    Default per-template thresholds come from config.toml[vision.thresholds].
    """

    def __init__(self, monitor_index: int | None = None, threshold: float | None = None):
        idx = monitor_index if monitor_index is not None else cfg.get("vision.monitor_index", 1)
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[idx]
        self.default_threshold: float = (
            threshold if threshold is not None else cfg.get("vision.default_threshold", 0.82)
        )
        self._template_cache: dict[str, np.ndarray] = {}
        self._win_id: str | None = None
        self._mss_broken = False  # latches once mss.grab fails, to skip retrying it

    def _threshold_for(self, template_name: str, override: float | None) -> float:
        """Resolves threshold: override > per-template config > default."""
        if override is not None:
            return override
        return float(cfg.get(f"vision.thresholds.{template_name}", self.default_threshold))

    def _game_window(self) -> str:
        """
        Cached Satisfactory window id (xdotool). Falls back to 'root'. Cached
        because the lookup spawns a process and the window id is stable for a
        session; if the window is gone the next grab will fail loudly anyway.
        """
        if self._win_id is None:
            out = subprocess.run(
                ["xdotool", "search", "--name", "Satisfactory"],
                capture_output=True,
                text=True,
            )
            ids = out.stdout.split()
            self._win_id = ids[0] if ids else "root"
        return self._win_id

    def _import_grab(self, region: tuple[int, int, int, int] | None = None) -> np.ndarray | None:
        """
        Grabs the game window (or a sub-region) via ImageMagick 'import',
        piped through stdout (no temp file). This is the ONLY capture path
        that actually sees the game on this KDE/Wayland box: the game is a
        GL/Xwayland surface that mss and x11grab read back as solid black,
        while a plain `import -window <gameWin>` forces a GL readback.

        Crucially, passing -crop makes 'import' read back ONLY that region:
        a full 2560x1440 grab costs ~7.5s, but a small HUD crop costs ~0.2s
        (measured live 2026-06-25). The per-chunk safety checks during
        exploration grab small regions for exactly this reason — a 7.5s
        freeze between movement chunks was itself the danger (the character
        stands still in a hazard, the Hover Pack drains, and it falls).
        """
        win = self._game_window()
        cmd = ["import", "-window", win]
        if region is not None:
            x, y, w, h = region
            cmd += ["-crop", f"{w}x{h}+{x}+{y}", "+repage"]
        cmd.append("png:-")
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0 or not proc.stdout:
            return None
        return cv2.imdecode(np.frombuffer(proc.stdout, np.uint8), cv2.IMREAD_COLOR)

    def capture(self) -> np.ndarray:
        """Captures the full frame. mss when it works, else a full 'import' grab (slow — prefer grab_region for HUD checks)."""
        if not self._mss_broken:
            try:
                raw = self.sct.grab(self.monitor)
                return cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
            except mss.exception.ScreenShotError:
                self._mss_broken = True
            except Exception:
                self._mss_broken = True
        frame = self._import_grab()
        if frame is None:
            raise RuntimeError("Full-screen capture failed (mss and import both unavailable).")
        return frame

    def grab_region(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        """
        Fast capture of a screen region (~0.2s) via a cropped 'import' grab.
        Used by read_player_status / death checks during movement so the
        character barely pauses. Falls back to cropping a full frame.
        """
        frame = self._import_grab((x, y, w, h))
        if frame is not None:
            return frame
        return self.capture()[y : y + h, x : x + w]

    def assess(self) -> tuple[dict, np.ndarray]:
        """
        Reads the live player HUD from the bottom-left in one fast grab and
        the death overlay from a second small center grab. Returns the status
        dict AND the bottom-left HUD image, so the caller can persist that
        same crop for dense visual debugging without a third grab.

        Replaces the old health_low_indicator check, which only matched the
        heart icon (present at ANY health) and was therefore meaningless.

        Status keys:
          health_segments : int 0..10  (lit segments of the health bar)
          health_frac     : float 0..1 (health_segments / 10)
          health_low      : bool       (health_frac <= low threshold)
          damage_red      : float      (red-vignette fraction in the corner —
                                        spikes while taking damage; baseline ~0.06)
          gauge_frac      : float|None (Hover Pack charge ring fill, best-effort)
          died            : bool       (death overlay detected)
        """
        hx, hy, hw, hh = _HEALTH_REGION
        region = self.grab_region(hx, hy, hw, hh)

        # --- health: count lit segments of the bar ---
        v = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)[:, :, 2].astype(float)
        y0, y1 = _HEALTH_BAR_Y
        lit = 0
        for sx0, sx1 in _HEALTH_SEGMENTS:
            seg = v[y0:y1, sx0:sx1]
            if seg.size and (seg > _HEALTH_BRIGHT_V).mean() > _HEALTH_SEGMENT_LIT_FRAC:
                lit += 1
        health_frac = lit / len(_HEALTH_SEGMENTS)

        # --- damage vignette: red bias in the corner we already grabbed ---
        b, g, r = (region[:, :, i].astype(int) for i in range(3))
        damage_red = float(((r - g > 40) & (r - b > 40)).mean())

        # --- hover gauge: best-effort fill of the charge ring (calibrated
        # live during flight; until then this is a logged metric, not a gate) ---
        gauge_frac = self._read_gauge_fraction()

        low_thr = cfg.get("exploration.health_low_frac", 0.4)
        status = {
            "health_segments": lit,
            "health_frac": health_frac,
            "health_low": health_frac <= low_thr,
            "damage_red": damage_red,
            "gauge_frac": gauge_frac,
            "died": self._death_overlay_present(),
        }
        return status, region

    def read_player_status(self) -> dict:
        """Status-only wrapper around assess() (drops the HUD image)."""
        status, _ = self.assess()
        return status

    def _read_gauge_fraction(self) -> float | None:
        """
        Hover Pack charge-ring fill (0..1) from its own fast grab of the
        bottom-left ring. The ring only renders while flying, so this returns
        None when the orange fan (inner disk) isn't present. When it is, the
        fraction is the portion of the white ring still lit — the charge left
        before the pack drops out of electric-pole range and the player falls.
        """
        gx, gy, gw, gh = _GAUGE_REGION
        sub = self.grab_region(gx, gy, gw, gh)
        if sub is None or sub.size == 0:
            return None
        hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
        cx, cy = _GAUGE_CENTER[0] - gx, _GAUGE_CENTER[1] - gy
        h_max, w_max = hsv.shape[:2]

        # Precompute 72 sample angles
        _N = 72
        angles = np.linspace(0, 2 * np.pi, _N, endpoint=False)
        cos_a = np.cos(angles)
        sin_a = np.sin(angles)

        def _sample_ring(radius: int):
            """Returns (V_means, S_means, H_means) arrays of shape (_N,) for ring at given radius."""
            xs = np.clip(np.round(cx + radius * cos_a).astype(int), 1, w_max - 2)
            ys = np.clip(np.round(cy + radius * sin_a).astype(int), 1, h_max - 2)
            v_vals = np.empty(_N)
            s_vals = np.empty(_N)
            h_vals = np.empty(_N)
            for k in range(_N):
                patch = hsv[max(ys[k] - 1, 0) : ys[k] + 2, max(xs[k] - 1, 0) : xs[k] + 2]
                if patch.size:
                    h_vals[k] = patch[:, :, 0].mean()
                    s_vals[k] = patch[:, :, 1].mean()
                    v_vals[k] = patch[:, :, 2].mean()
                else:
                    h_vals[k] = s_vals[k] = v_vals[k] = 0.0
            return v_vals, s_vals, h_vals

        # GATE: the charge ring is shared by two icons that render here -- the
        # spinning Hover Pack fan (flying) and the objective-complete checkmark
        # (grounded). Both have a full white ring, so ring-presence alone is not
        # enough. The fan has a DARK central hub (all-dark thin ring at r=10,
        # rotation-invariant); the checkmark has an orange centre (~0.3 dark).
        # Require the dark hub AND orange blades at mid-radius (rules out an
        # empty/dark corner). This holds at any charge level, so a near-empty
        # gauge (the dangerous moment) still reads instead of gating to None.

        # GATE: dark hub at r=10
        v10, _, _ = _sample_ring(10)
        hub_dark = float((v10 < 110).mean())

        # Orange blades at mid-radius r=14
        v14, s14, h14 = _sample_ring(14)
        orange_mid = float(((h14 >= 5) & (h14 <= 30) & (s14 > 90) & (v14 > 110)).mean())

        if hub_dark < 0.6 or orange_mid < 0.2:
            return None  # checkmark / empty corner -> not flying

        # Charge = portion of the white ring still lit
        v_ring, s_ring, _ = _sample_ring(_GAUGE_RADIUS)
        return float(((v_ring > _GAUGE_RING_VBRIGHT) & (s_ring < _GAUGE_RING_SMAX)).mean())

    def _death_overlay_present(self) -> bool:
        """Matches the death overlay in a small center grab; missing template = unknown (False)."""
        try:
            template = self._load_template("death_screen")
        except FileNotFoundError:
            return False
        dx, dy, dw, dh = _DEATH_REGION
        region = self.grab_region(dx, dy, dw, dh)
        th, tw = template.shape[:2]
        if region.shape[0] < th or region.shape[1] < tw:
            return False
        res = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        return bool(max_val >= float(cfg.get("vision.thresholds.death_screen", 0.60)))

    def _load_template(self, template_name: str) -> np.ndarray:
        if template_name not in self._template_cache:
            path = TEMPLATES_DIR / f"{template_name}.png"
            if not path.exists():
                raise FileNotFoundError(
                    f"Template '{template_name}.png' not found in {TEMPLATES_DIR}.\n"
                    "Run: uv run python capture_template.py"
                )
            tmpl = cv2.imread(str(path))
            if tmpl is None:
                raise ValueError(f"Failed to load image: {path}")
            self._template_cache[template_name] = tmpl
        return self._template_cache[template_name]

    def find(
        self,
        template_name: str,
        frame: np.ndarray | None = None,
        threshold: float | None = None,
    ) -> MatchResult:
        """
        Looks for a template on screen.
        threshold: if None, uses the value from config.toml[vision.thresholds.{name}] or default.
        """
        if frame is None:
            frame = self.capture()

        template = self._load_template(template_name)
        thr = self._threshold_for(template_name, threshold)

        result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= thr:
            th, tw = template.shape[:2]
            cx = max_loc[0] + tw // 2
            cy = max_loc[1] + th // 2
            return MatchResult(found=True, x=cx, y=cy, confidence=max_val, template_name=template_name)

        return MatchResult(found=False, confidence=max_val, template_name=template_name)

    def wait_for(
        self,
        template_name: str,
        timeout: float = 10.0,
        poll_interval: float = 0.1,
        threshold: float | None = None,
    ) -> MatchResult:
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self.find(template_name, threshold=threshold)
            if result.found:
                return result
            time.sleep(poll_interval)
        return MatchResult(found=False, template_name=template_name)

    def find_enemy(self, frame: np.ndarray | None = None) -> MatchResult | None:
        # Hazard variants (area damage — radiation/gas) first, to prioritize
        # hazard detection over their equivalent common variant.
        enemy_templates = [
            "enemy_hog_nuclear",
            "enemy_stinger_elite_gas",
            "enemy_spitter",
            "enemy_hog",
            "enemy_stinger",
            "enemy_spitter_elite",
            "enemy_hatcher",
            "enemy_flying_crab",
        ]
        if frame is None:
            frame = self.capture()

        for name in enemy_templates:
            try:
                result = self.find(name, frame=frame)
                if result.found:
                    return result
            except FileNotFoundError:
                pass

        return None

    def scan_all(
        self,
        template_names: list[str],
        threshold: float | None = None,
    ) -> dict[str, MatchResult]:
        """Scans multiple templates in a single capture."""
        frame = self.capture()
        results: dict[str, MatchResult] = {}
        for name in template_names:
            try:
                results[name] = self.find(name, frame=frame, threshold=threshold)
            except FileNotFoundError:
                results[name] = MatchResult(found=False, confidence=-1.0, template_name=name)
        return results

    def read_text_region(self, x: int, y: int, w: int, h: int) -> str:
        try:
            import pytesseract

            region = self.grab_region(x, y, w, h)
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
            return str(pytesseract.image_to_string(binary, config="--psm 7 digits").strip())
        except Exception:
            return ""


_shared_instance: Vision | None = None


def get_shared() -> Vision:
    """Returns a shared Vision instance (singleton). Use this instead of creating new Vision() instances."""
    global _shared_instance
    if _shared_instance is None:
        _shared_instance = Vision()
    return _shared_instance
