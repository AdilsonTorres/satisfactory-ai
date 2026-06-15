"""
utils/vision.py
Captura de tela e detecção visual via template matching.
Sem ML, sem cloud. Tudo local com OpenCV.
"""
import time
import numpy as np
import cv2
import mss
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


@dataclass
class MatchResult:
    found: bool
    x: int = 0
    y: int = 0
    confidence: float = 0.0

    @property
    def center(self) -> tuple[int, int]:
        return self.x, self.y


class Vision:
    """
    Wrapper de visão computacional local.
    Usa template matching do OpenCV — zero GPU, zero treinamento.
    """

    def __init__(self, monitor_index: int = 1, threshold: float = 0.80):
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[monitor_index]
        self.threshold = threshold
        self._template_cache: dict[str, np.ndarray] = {}

    def capture(self) -> np.ndarray:
        """Captura o frame atual da tela. ~1ms."""
        raw = self.sct.grab(self.monitor)
        frame = np.array(raw)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def capture_region(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        """Captura só uma região — útil para checar menus específicos."""
        region = {"top": y, "left": x, "width": w, "height": h}
        raw = self.sct.grab(region)
        frame = np.array(raw)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def _load_template(self, template_name: str) -> np.ndarray:
        """Carrega e cacheia template de disco."""
        if template_name not in self._template_cache:
            path = TEMPLATES_DIR / f"{template_name}.png"
            if not path.exists():
                raise FileNotFoundError(
                    f"Template '{template_name}.png' não encontrado em {TEMPLATES_DIR}.\n"
                    f"Tire um print do elemento no jogo e salve lá."
                )
            tmpl = cv2.imread(str(path))
            self._template_cache[template_name] = tmpl
        return self._template_cache[template_name]

    def find(self, template_name: str, frame: Optional[np.ndarray] = None,
             threshold: Optional[float] = None) -> MatchResult:
        """Procura um template na tela. Retorna MatchResult com posição central do match."""
        if frame is None:
            frame = self.capture()

        template = self._load_template(template_name)
        thr = threshold or self.threshold

        result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= thr:
            th, tw = template.shape[:2]
            cx = max_loc[0] + tw // 2
            cy = max_loc[1] + th // 2
            return MatchResult(found=True, x=cx, y=cy, confidence=max_val)

        return MatchResult(found=False, confidence=max_val)

    def wait_for(self, template_name: str, timeout: float = 10.0,
                 poll_interval: float = 0.1) -> MatchResult:
        """Aguarda um template aparecer na tela até `timeout` segundos."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self.find(template_name)
            if result.found:
                return result
            time.sleep(poll_interval)
        return MatchResult(found=False)

    def find_enemy(self, frame: Optional[np.ndarray] = None) -> Optional[MatchResult]:
        """Tenta encontrar inimigos conhecidos na tela."""
        enemy_templates = [
            "enemy_spitter",
            "enemy_hog",
            "enemy_stinger",
            "enemy_spitter_elite",
        ]
        if frame is None:
            frame = self.capture()

        for tmpl_name in enemy_templates:
            try:
                result = self.find(tmpl_name, frame=frame, threshold=0.70)
                if result.found:
                    return result
            except FileNotFoundError:
                pass  # Template ainda não criado, pula

        return None

    def read_text_region(self, x: int, y: int, w: int, h: int) -> str:
        """
        OCR em uma região específica da tela.
        Requer pytesseract instalado e Tesseract no PATH.
        """
        try:
            import pytesseract
            region = self.capture_region(x, y, w, h)
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
            return pytesseract.image_to_string(binary, config="--psm 7 digits").strip()
        except Exception:
            return ""
