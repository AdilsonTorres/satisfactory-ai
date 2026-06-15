"""
utils/vision.py
Captura de tela e detecção visual via template matching.
Thresholds são lidos automaticamente de config.toml por template.
"""
import time
import numpy as np
import cv2
import mss
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from utils import config as cfg

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


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
    Wrapper de visão computacional local.
    Thresholds padrão por template veem de config.toml[vision.thresholds].
    """

    def __init__(self, monitor_index: Optional[int] = None, threshold: Optional[float] = None):
        idx = monitor_index if monitor_index is not None else cfg.get("vision.monitor_index", 1)
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[idx]
        self.default_threshold: float = threshold if threshold is not None else cfg.get(
            "vision.default_threshold", 0.82
        )
        self._template_cache: dict[str, np.ndarray] = {}

    def _threshold_for(self, template_name: str, override: Optional[float]) -> float:
        """Resolve threshold: override > config por template > default."""
        if override is not None:
            return override
        return cfg.get(f"vision.thresholds.{template_name}", self.default_threshold)

    def capture(self) -> np.ndarray:
        """Captura o frame atual. ~1ms."""
        raw = self.sct.grab(self.monitor)
        frame = np.array(raw)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def capture_region(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        region = {"top": y, "left": x, "width": w, "height": h}
        raw = self.sct.grab(region)
        return cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)

    def _load_template(self, template_name: str) -> np.ndarray:
        if template_name not in self._template_cache:
            path = TEMPLATES_DIR / f"{template_name}.png"
            if not path.exists():
                raise FileNotFoundError(
                    f"Template '{template_name}.png' não encontrado em {TEMPLATES_DIR}.\n"
                    "Execute: uv run python capture_template.py"
                )
            tmpl = cv2.imread(str(path))
            if tmpl is None:
                raise ValueError(f"Falha ao carregar imagem: {path}")
            self._template_cache[template_name] = tmpl
        return self._template_cache[template_name]

    def find(
        self,
        template_name: str,
        frame: Optional[np.ndarray] = None,
        threshold: Optional[float] = None,
    ) -> MatchResult:
        """
        Procura template na tela.
        threshold: se None, usa valor de config.toml[vision.thresholds.{name}] ou default.
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
        threshold: Optional[float] = None,
    ) -> MatchResult:
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self.find(template_name, threshold=threshold)
            if result.found:
                return result
            time.sleep(poll_interval)
        return MatchResult(found=False, template_name=template_name)

    def find_enemy(self, frame: Optional[np.ndarray] = None) -> Optional[MatchResult]:
        enemy_templates = [
            "enemy_spitter",
            "enemy_hog",
            "enemy_stinger",
            "enemy_spitter_elite",
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
        threshold: Optional[float] = None,
    ) -> dict[str, MatchResult]:
        """Escaneia múltiplos templates em uma única captura."""
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
            region = self.capture_region(x, y, w, h)
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
            return pytesseract.image_to_string(binary, config="--psm 7 digits").strip()
        except Exception:
            return ""
