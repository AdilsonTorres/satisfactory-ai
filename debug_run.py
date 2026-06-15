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

from utils.vision import Vision
from utils.screenshot import save_debug_screenshot, save_annotated_screenshot
from utils import config as cfg

ALL_TEMPLATES = [
    "gift_prompt",
    "inventory_open",
    "inventory_full_indicator",
    "health_low_indicator",
    "equipment_workshop_prompt",
    "workshop_menu_open",
    "rifle_ammo_icon",
    "craft_button",
    "death_screen",
    "respawn_button",
    "enemy_remains_prompt",
    "enemy_spitter",
    "enemy_hog",
    "enemy_stinger",
    "enemy_spitter_elite",
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
  uv run python debug_run.py --screenshot
  uv run python debug_run.py --config
""",
    )
    parser.add_argument("--scan",       action="store_true", help="Escaneia todos os templates")
    parser.add_argument("--find",       metavar="TEMPLATE",  help="Procura um template")
    parser.add_argument("--screenshot", action="store_true", help="Screenshot da tela atual")
    parser.add_argument("--config",     action="store_true", help="Exibe config.toml atual")
    parser.add_argument("--threshold",  type=float,          help="Override de threshold")

    args = parser.parse_args()

    if args.scan:
        cmd_scan(args.threshold)
    elif args.find:
        cmd_find(args.find, args.threshold)
    elif args.screenshot:
        cmd_screenshot()
    elif args.config:
        cmd_config()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
