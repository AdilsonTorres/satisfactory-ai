"""
capture_template.py

Script auxiliar para capturar templates do jogo.
Roda fora do Temporal — é só uma ferramenta de setup.

Uso:
    uv run python capture_template.py

Pressione SPACE para capturar uma região da tela.
A região será salva em templates/ com o nome que você definir.
"""
import time
import numpy as np
import cv2
import mss
from pathlib import Path

TEMPLATES_DIR = Path("templates")
TEMPLATES_DIR.mkdir(exist_ok=True)


def capture_fullscreen() -> np.ndarray:
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
        frame = np.array(raw)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)


def select_roi_and_save(name: str):
    """Captura tela e deixa o usuário selecionar uma região com o mouse."""
    print(f"\nCapturando tela para o template '{name}'...")
    print("Posicione o jogo na tela e aguarde 2 segundos...")
    time.sleep(2)

    frame = capture_fullscreen()

    print("Selecione a região com o mouse. Pressione ENTER para confirmar ou C para cancelar.")
    roi = cv2.selectROI(f"Selecione: {name}", frame, fromCenter=False, showCrosshair=True)
    cv2.destroyAllWindows()

    x, y, w, h = roi
    if w == 0 or h == 0:
        print("Cancelado.")
        return

    cropped = frame[y:y+h, x:x+w]
    out_path = TEMPLATES_DIR / f"{name}.png"
    cv2.imwrite(str(out_path), cropped)
    print(f"Salvo em {out_path} ({w}x{h} pixels)")


TEMPLATES_NEEDED = [
    # Gifts e inventário
    ("gift_prompt",              "Ícone/texto de interação que aparece quando o Doggo tem gift"),
    ("inventory_open",           "Qualquer elemento que indica o inventário está aberto"),
    ("inventory_full_indicator", "Indicador visual de inventário cheio"),
    ("health_low_indicator",     "Barra de vida quando está baixa (vermelho)"),

    # Workshop
    ("equipment_workshop_prompt", "Prompt de interação E no Equipment Workshop"),
    ("workshop_menu_open",        "Elemento do menu do Workshop quando aberto"),
    ("rifle_ammo_icon",           "Ícone da Rifle Ammo no menu de craft"),
    ("craft_button",              "Botão de craft no Workshop"),

    # Combate
    ("enemy_spitter",        "Silhueta/indicador de Spitter na tela"),
    ("enemy_hog",            "Silhueta/indicador de Alpha Hog na tela"),
    ("enemy_remains_prompt", "Prompt E para lotar os remains do inimigo morto"),
    ("death_screen",         "Tela de morte do personagem"),
    ("respawn_button",       "Botão de respawn na tela de morte"),
]


def main():
    print("=" * 60)
    print("  Satisfactory Bot — Capturador de Templates")
    print("=" * 60)
    print(f"\nTemplates serão salvos em: {TEMPLATES_DIR.absolute()}")
    print("\nVocê precisa criar os seguintes templates:")

    for name, desc in TEMPLATES_NEEDED:
        exists = (TEMPLATES_DIR / f"{name}.png").exists()
        status = "OK" if exists else "--"
        print(f"  [{status}] {name:<35} — {desc}")

    print("\n" + "=" * 60)

    missing = [(n, d) for n, d in TEMPLATES_NEEDED if not (TEMPLATES_DIR / f"{n}.png").exists()]

    if not missing:
        print("\nTodos os templates já existem!")
        return

    print(f"\n{len(missing)} templates faltando. Vamos capturá-los.")
    print("(Você pode fechar com Ctrl+C a qualquer momento e continuar depois)")

    for name, desc in missing:
        print(f"\n{'=' * 60}")
        print(f"Template: {name}")
        print(f"O que é: {desc}")
        resp = input("Capturar agora? [s/N] ").strip().lower()
        if resp == "s":
            select_roi_and_save(name)
        else:
            print("Pulando.")

    print("\nSessão de captura finalizada.")
    print("Templates criados:")
    for f in sorted(TEMPLATES_DIR.glob("*.png")):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
