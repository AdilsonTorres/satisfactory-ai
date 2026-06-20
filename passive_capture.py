"""
passive_capture.py

Captura screenshots periodicamente enquanto você joga normalmente.
NÃO envia nenhum input (teclado/mouse) — seguro para rodar em paralelo
com o jogo enquanto você joga manualmente.

Frames quase idênticos ao último salvo são descartados (dedup por diff em
baixa resolução), para não acumular centenas de screenshots do mesmo menu
parado.

Depois de uma sessão de jogo, use label_captures.py para revisar as imagens
em captures/ e recortar novos templates ou variantes para os existentes.

Uso:
    uv run python passive_capture.py
    uv run python passive_capture.py --interval 5 --max-shots 200
    uv run python passive_capture.py --dedup-threshold 0.0   # salva tudo, sem dedup
"""
import argparse
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from utils.vision import Vision

CAPTURES_DIR = Path("captures")


def _frames_differ(a: np.ndarray, b: np.ndarray, threshold: float) -> bool:
    """Compara dois frames reduzidos; True se diferentes o suficiente para valer salvar de novo."""
    small_a = cv2.resize(a, (64, 36))
    small_b = cv2.resize(b, (64, 36))
    diff = cv2.absdiff(small_a, small_b)
    score = float(np.mean(diff)) / 255.0
    return score > threshold


def run(interval: float, max_shots: int, dedup_threshold: float) -> None:
    CAPTURES_DIR.mkdir(exist_ok=True)
    v = Vision()
    last_frame = None
    saved = 0

    print(f"Captura passiva iniciada — a cada {interval}s, salvando em {CAPTURES_DIR}/")
    print("Ctrl+C para parar. Nenhum input é enviado ao jogo — pode jogar normalmente.\n")

    try:
        while max_shots <= 0 or saved < max_shots:
            frame = v.capture()
            if last_frame is None or _frames_differ(frame, last_frame, dedup_threshold):
                ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
                path = CAPTURES_DIR / f"{ts}.png"
                cv2.imwrite(str(path), frame)
                saved += 1
                last_frame = frame
                print(f"[{saved}] {path.name}")
            time.sleep(interval)
    except KeyboardInterrupt:
        pass

    print(f"\nEncerrado. {saved} screenshot(s) salvo(s) em {CAPTURES_DIR}/")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Captura passiva de screenshots durante gameplay manual (sem enviar input).",
    )
    parser.add_argument("--interval", type=float, default=4.0, help="Segundos entre capturas [4.0]")
    parser.add_argument("--max-shots", type=int, default=0, help="Limite de screenshots, 0 = sem limite [0]")
    parser.add_argument(
        "--dedup-threshold", type=float, default=0.02,
        help="Sensibilidade de deduplicação — 0 desativa (salva todo frame) [0.02]"
    )
    args = parser.parse_args()
    run(args.interval, args.max_shots, args.dedup_threshold)


if __name__ == "__main__":
    main()
