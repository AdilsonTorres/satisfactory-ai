"""
capture_template.py

Script auxiliar para capturar templates do jogo.
Roda fora do Temporal — é só uma ferramenta de setup.

Uso:
    uv run python capture_template.py

Pressione ENTER para confirmar a região selecionada, C para cancelar.
"""
import os
import time
import numpy as np

# O Qt embutido no cv2 só traz o plugin "xcb" — em sessões Wayland ele tenta
# "wayland" por padrão e a janela de seleção de ROI fica sem receber clique
# nenhum. Força xcb (via XWayland) e desativa o auto-scaling de HiDPI do Qt,
# que também desalinha onde o clique é registrado.
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
os.environ.setdefault("QT_SCALE_FACTOR", "1")

import cv2
import mss
from pathlib import Path

TEMPLATES_DIR = Path("templates")
TEMPLATES_DIR.mkdir(exist_ok=True)

# Tamanho máximo de janela na tela — screenshots em 2560x1440+ não cabem
# inteiros na maioria das telas. cv2.selectROI mapeia o ROI de volta para
# a resolução original da imagem, então o recorte salvo continua em
# resolução nativa mesmo com a janela exibida menor.
_MAX_WINDOW_W = 1600
_MAX_WINDOW_H = 900


def capture_fullscreen() -> np.ndarray:
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
        frame = np.array(raw)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)


def select_roi_and_save(name: str) -> bool:
    """Captura tela e deixa o usuário selecionar uma região com o mouse."""
    print(f"\nCapturando em 2s para o template '{name}'...")
    time.sleep(2)

    frame = capture_fullscreen()
    window = f"Selecione: {name}"
    h, w = frame.shape[:2]
    scale = min(_MAX_WINDOW_W / w, _MAX_WINDOW_H / h, 1.0)
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, int(w * scale), int(h * scale))
    roi = cv2.selectROI(window, frame, fromCenter=False, showCrosshair=True)
    cv2.destroyAllWindows()

    x, y, w, h = roi
    if w == 0 or h == 0:
        print("Cancelado.")
        return False

    cropped = frame[y:y+h, x:x+w]
    out_path = TEMPLATES_DIR / f"{name}.png"
    cv2.imwrite(str(out_path), cropped)
    print(f"Salvo: {out_path} ({w}x{h}px)")
    return True


TEMPLATES_NEEDED = [
    ("gift_prompt",               "Ícone/texto de interação quando o Doggo tem gift"),
    ("inventory_open",            "Elemento que indica o inventário está aberto"),
    ("doggo_loot_window",         "Janela de loot (1 slot) do próprio Doggo, ao interagir com E"),
    ("wild_doggo_prompt",         "Silhueta de um Lizard Doggo selvagem (ainda não domesticado) na tela"),
    ("paleberry_icon",            "Ícone da Paleberry no inventário aberto"),
    ("inventory_full_indicator",  "Indicador visual de inventário cheio"),
    ("health_low_indicator",      "Barra de vida baixa (vermelho)"),
    ("equipment_workshop_prompt", "Prompt E no Equipment Workshop"),
    ("workshop_menu_open",        "Elemento do menu do Workshop aberto"),
    ("rifle_ammo_icon",           "Ícone da Rifle Ammo no menu de craft"),
    ("craft_button",              "Botão de craft no Workshop"),
    ("enemy_spitter",             "Silhueta de Spitter na tela"),
    ("enemy_hog",                 "Silhueta de Alpha Hog na tela"),
    ("enemy_stinger",             "Silhueta de Stinger na tela"),
    ("enemy_spitter_elite",       "Silhueta de Spitter Elite na tela"),
    ("enemy_hatcher",             "Silhueta de Flying Crab Hatcher (ninho) na tela"),
    ("enemy_flying_crab",         "Silhueta de Flying Crab na tela"),
    ("enemy_hog_nuclear",         "HAZARD: Cliff Hog Nuclear/irradiado — dano em área de radiação"),
    ("enemy_stinger_elite_gas",   "HAZARD: Elite Gas Stinger — emite gás venenoso em área"),
    ("enemy_remains_prompt",      "Prompt E para lotar os remains"),
    ("resource_node_prompt",      "Prompt de interação ao olhar para um node de recurso no alcance"),
    ("storage_prompt",            "Prompt de interação ao olhar para um storage container no alcance"),
    ("storage_open",              "Elemento que indica a janela do storage container está aberta"),
    ("death_screen",              "Tela de morte do personagem"),
    ("respawn_button",            "Botão de respawn na tela de morte"),
]


def main() -> None:
    print("=" * 60)
    print("  Satisfactory Bot — Capturador de Templates")
    print("=" * 60)
    print(f"\nSalvando em: {TEMPLATES_DIR.absolute()}\n")

    for name, desc in TEMPLATES_NEEDED:
        exists = (TEMPLATES_DIR / f"{name}.png").exists()
        status = "OK" if exists else "--"
        print(f"  [{status}] {name:<35}  {desc}")

    missing = [(n, d) for n, d in TEMPLATES_NEEDED if not (TEMPLATES_DIR / f"{n}.png").exists()]

    if not missing:
        print("\nTodos os templates existem!")
        return

    print(f"\n{len(missing)} templates faltando.")
    print("Ctrl+C a qualquer momento para continuar depois.\n")

    for name, desc in missing:
        print(f"{'─' * 60}")
        print(f"Template : {name}")
        print(f"O que é  : {desc}")
        resp = input("Capturar agora? [s/N] ").strip().lower()
        if resp == "s":
            select_roi_and_save(name)

    print("\nSessão finalizada. Templates em debug_screenshots/ para conferir.")
    for f in sorted(TEMPLATES_DIR.glob("*.png")):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
