"""
debug_run.py

Testa visão e templates SEM o Temporal rodando.
Execute antes do worker para confirmar que os templates funcionam.

Uso:
    uv run python debug_run.py --scan
    uv run python debug_run.py --find gift_prompt
    uv run python debug_run.py --find enemy_spitter --threshold 0.65
    uv run python debug_run.py --screenshot
    uv run python debug_run.py --config
"""
import argparse
import json
import sys
from pathlib import Path

import cv2

from utils.vision import Vision
from utils.screenshot import save_debug_screenshot, save_annotated_screenshot
from utils import config as cfg

ALL_TEMPLATES = [
    "gift_prompt",
    "inventory_open",
    "doggo_loot_window",
    "wild_doggo_prompt",
    "paleberry_icon",
    "inventory_full_indicator",
    "health_low_indicator",
    "equipment_workshop_prompt",
    "workshop_menu_open",
    "rifle_ammo_icon",
    "craft_button",
    "death_screen",
    "respawn_button",
    "enemy_remains_prompt",
    "resource_node_prompt",
    "storage_prompt",
    "storage_open",
    "enemy_spitter",
    "enemy_hog",
    "enemy_stinger",
    "enemy_spitter_elite",
    "enemy_hatcher",
    "enemy_flying_crab",
    "enemy_hog_nuclear",
    "enemy_stinger_elite_gas",
]


def cmd_scan(threshold_override: float | None = None) -> None:
    """Escaneia todos os templates e salva screenshot anotado."""
    v = Vision()
    frame = v.capture()

    print(f"\nEscaneando tela...\n")
    print(f"{'Template':<35} {'Status':<8} {'Conf':>6}  {'Threshold':>9}  {'Posição'}")
    print("─" * 75)

    found: dict[str, tuple[int, int, float]] = {}
    missing_files: list[str] = []

    for name in ALL_TEMPLATES:
        thr = threshold_override if threshold_override is not None else (
            cfg.get(f"vision.thresholds.{name}") or cfg.get("vision.default_threshold", 0.82)
        )
        try:
            r = v.find(name, frame=frame, threshold=thr)
            status = "FOUND" if r.found else "miss"
            pos = f"({r.x:4d},{r.y:4d})" if r.found else ""
            print(f"{name:<35} {status:<8} {r.confidence:>6.3f}  {thr:>9.3f}  {pos}")
            if r.found:
                found[name] = (r.x, r.y, r.confidence)
        except FileNotFoundError:
            missing_files.append(name)
            print(f"{name:<35} [sem templates/{name}.png]")

    print()
    raw = save_debug_screenshot("scan", frame=frame)
    print(f"Screenshot:         {raw}")

    if found:
        ann = save_annotated_screenshot("scan", found, frame=frame)
        print(f"Screenshot anotado: {ann}")

    print(f"\n{len(found)}/{len(ALL_TEMPLATES) - len(missing_files)} encontrados na tela.")
    if missing_files:
        print(f"{len(missing_files)} sem arquivo PNG — rode: uv run python capture_template.py")


def cmd_find(template_name: str, threshold_override: float | None = None) -> None:
    """Procura um template específico e mostra a confiança."""
    v = Vision()
    thr = threshold_override if threshold_override is not None else (
        cfg.get(f"vision.thresholds.{template_name}") or cfg.get("vision.default_threshold", 0.82)
    )

    print(f"\nProcurando '{template_name}' (threshold={thr:.3f})...")

    try:
        frame = v.capture()
        r = v.find(template_name, frame=frame, threshold=thr)
        if r.found:
            print(f"ENCONTRADO em ({r.x}, {r.y}) — conf: {r.confidence:.3f}")
            ann = save_annotated_screenshot(
                f"find_{template_name}",
                {template_name: (r.x, r.y, r.confidence)},
                frame=frame,
            )
            print(f"Screenshot anotado: {ann}")
        else:
            print(f"Não encontrado. Melhor conf: {r.confidence:.3f} (threshold: {thr:.3f})")
            gap = thr - r.confidence
            if gap < 0.08:
                suggestion = max(r.confidence - 0.02, 0.50)
                print(f"Dica: tente --threshold {suggestion:.2f} (conf está perto do threshold)")
            raw = save_debug_screenshot(f"notfound_{template_name}", frame=frame)
            print(f"Screenshot: {raw}")
    except FileNotFoundError as exc:
        print(f"Erro: {exc}")
        sys.exit(1)


def cmd_scan_dir(directory: str, threshold_override: float | None = None) -> None:
    """
    Roda todos os templates sobre cada imagem de um diretório (ex: captures/
    gerado por passive_capture.py) e resume a taxa de detecção de cada um.
    Útil para validar/ajustar thresholds contra screenshots reais de
    gameplay, em vez de só a tela atual.
    """
    v = Vision()
    paths = sorted(Path(directory).glob("*.png"))
    if not paths:
        print(f"Nenhuma imagem PNG em {directory}/")
        return

    tally: dict[str, int] = {name: 0 for name in ALL_TEMPLATES}
    missing_files: set[str] = set()
    scanned = 0

    for p in paths:
        frame = cv2.imread(str(p))
        if frame is None:
            continue
        scanned += 1
        for name in ALL_TEMPLATES:
            if name in missing_files:
                continue
            thr = threshold_override if threshold_override is not None else (
                cfg.get(f"vision.thresholds.{name}") or cfg.get("vision.default_threshold", 0.82)
            )
            try:
                r = v.find(name, frame=frame, threshold=thr)
                if r.found:
                    tally[name] += 1
            except FileNotFoundError:
                missing_files.add(name)

    print(f"\n{scanned} imagem(ns) escaneada(s) em {directory}/\n")
    print(f"{'Template':<35} {'Encontrado em'}")
    print("─" * 55)
    for name, count in tally.items():
        if name in missing_files:
            continue
        pct = (count / scanned * 100) if scanned else 0.0
        print(f"{name:<35} {count:>6}/{scanned} ({pct:5.1f}%)")

    if missing_files:
        print(f"\n{len(missing_files)} sem arquivo PNG ainda: {', '.join(sorted(missing_files))}")


def cmd_screenshot() -> None:
    path = save_debug_screenshot("manual")
    print(f"Screenshot: {path}")


def cmd_config() -> None:
    """Exibe a configuração atual de config.toml."""
    try:
        data = cfg.load()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except FileNotFoundError as exc:
        print(f"Erro: {exc}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Debug de templates — rode sem o Temporal rodando",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  uv run python debug_run.py --scan
  uv run python debug_run.py --find gift_prompt
  uv run python debug_run.py --find enemy_spitter --threshold 0.65
  uv run python debug_run.py --scan-dir captures
  uv run python debug_run.py --screenshot
  uv run python debug_run.py --config
""",
    )
    parser.add_argument("--scan",       action="store_true", help="Escaneia todos os templates")
    parser.add_argument("--find",       metavar="TEMPLATE",  help="Procura um template")
    parser.add_argument("--scan-dir",   metavar="DIR",       help="Roda --scan sobre cada PNG de um diretório (ex: captures/)")
    parser.add_argument("--screenshot", action="store_true", help="Screenshot da tela atual")
    parser.add_argument("--config",     action="store_true", help="Exibe config.toml atual")
    parser.add_argument("--threshold",  type=float,          help="Override de threshold")

    args = parser.parse_args()

    if args.scan:
        cmd_scan(args.threshold)
    elif args.find:
        cmd_find(args.find, args.threshold)
    elif args.scan_dir:
        cmd_scan_dir(args.scan_dir, args.threshold)
    elif args.screenshot:
        cmd_screenshot()
    elif args.config:
        cmd_config()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
