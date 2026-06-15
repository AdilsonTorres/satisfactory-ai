"""
debug_run.py

Testa visão e templates sem precisar do Temporal rodando.
Execute antes de ligar o worker para verificar que os templates estão corretos.

Uso:
    uv run python debug_run.py --scan
    uv run python debug_run.py --find enemy_spitter
    uv run python debug_run.py --find gift_prompt --threshold 0.70
    uv run python debug_run.py --screenshot
"""
import argparse
import sys
from pathlib import Path

from utils.vision import Vision
from utils.screenshot import save_debug_screenshot, save_annotated_screenshot

ALL_TEMPLATES = [
    "gift_prompt",
    "inventory_open",
    "inventory_full_indicator",
    "health_low_indicator",
    "equipment_workshop_prompt",
    "workshop_menu_open",
    "rifle_ammo_icon",
    "craft_button",
    "enemy_spitter",
    "enemy_hog",
    "enemy_stinger",
    "enemy_spitter_elite",
    "enemy_remains_prompt",
    "death_screen",
    "respawn_button",
]


def cmd_scan(threshold: float) -> None:
    """Escaneia todos os templates na tela atual e salva screenshot anotado."""
    v = Vision(threshold=threshold)
    frame = v.capture()

    print(f"\nEscaneando tela com threshold={threshold}...\n")
    print(f"{'Template':<35} {'Status':<8} {'Conf':>6}  {'Posição'}")
    print("─" * 65)

    found: dict[str, tuple[int, int, float]] = {}
    missing_files: list[str] = []

    for name in ALL_TEMPLATES:
        try:
            r = v.find(name, frame=frame)
            status = "FOUND " if r.found else "miss  "
            pos = f"({r.x:4d}, {r.y:4d})" if r.found else ""
            print(f"{name:<35} {status} {r.confidence:>6.3f}  {pos}")
            if r.found:
                found[name] = (r.x, r.y, r.confidence)
        except FileNotFoundError:
            missing_files.append(name)
            print(f"{name:<35} [sem PNG em templates/]")

    print()
    raw_path = save_debug_screenshot("scan", frame=frame)
    print(f"Screenshot salvo    : {raw_path}")

    if found:
        ann_path = save_annotated_screenshot("scan", found, frame=frame)
        print(f"Screenshot anotado  : {ann_path}")

    if missing_files:
        print(f"\n{len(missing_files)} template(s) sem arquivo PNG — rode: uv run python capture_template.py")

    print(f"\n{len(found)}/{len(ALL_TEMPLATES)} templates encontrados na tela.")


def cmd_find(template_name: str, threshold: float) -> None:
    """Procura um template específico e salva screenshot."""
    v = Vision(threshold=threshold)
    print(f"\nProcurando '{template_name}' (threshold={threshold})...")

    try:
        frame = v.capture()
        r = v.find(template_name, frame=frame, threshold=threshold)
        if r.found:
            print(f"ENCONTRADO em ({r.x}, {r.y}) — confiança: {r.confidence:.3f}")
            ann_path = save_annotated_screenshot(
                f"find_{template_name}", {template_name: (r.x, r.y, r.confidence)}, frame=frame
            )
            print(f"Screenshot anotado: {ann_path}")
        else:
            print(f"Não encontrado. Melhor conf: {r.confidence:.3f} (threshold: {threshold})")
            if r.confidence > threshold * 0.85:
                print(f"Dica: tente --threshold {r.confidence - 0.02:.2f} para capturar com margem menor.")
            raw_path = save_debug_screenshot(f"notfound_{template_name}", frame=frame)
            print(f"Screenshot: {raw_path}")
    except FileNotFoundError as exc:
        print(f"Erro: {exc}")
        sys.exit(1)


def cmd_screenshot() -> None:
    """Tira um screenshot simples da tela atual."""
    path = save_debug_screenshot("manual")
    print(f"Screenshot salvo: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Debug de templates do Satisfactory Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  uv run python debug_run.py --scan
  uv run python debug_run.py --find gift_prompt
  uv run python debug_run.py --find enemy_spitter --threshold 0.65
  uv run python debug_run.py --screenshot
""",
    )
    parser.add_argument("--scan", action="store_true", help="Escaneia todos os templates na tela atual")
    parser.add_argument("--find", metavar="TEMPLATE", help="Procura um template específico")
    parser.add_argument("--screenshot", action="store_true", help="Tira um screenshot da tela atual")
    parser.add_argument("--threshold", type=float, default=0.80, help="Threshold de confiança (default: 0.80)")

    args = parser.parse_args()

    if args.scan:
        cmd_scan(args.threshold)
    elif args.find:
        cmd_find(args.find, args.threshold)
    elif args.screenshot:
        cmd_screenshot()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
