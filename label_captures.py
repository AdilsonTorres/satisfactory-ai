"""
label_captures.py

Ferramenta de classificação manual: percorre os screenshots salvos por
passive_capture.py (em captures/) e deixa você recortar regiões para criar
ou atualizar templates em templates/. Roda fora do Temporal — ferramenta de
setup, no mesmo espírito de capture_template.py, mas sobre imagens já
capturadas em vez de uma captura ao vivo.

Por imagem, no prompt:
    [Enter]       pula para a próxima
    <nome>        recorta uma região e salva/sobrescreve templates/<nome>.png
    d             descarta a imagem (apaga o arquivo)
    q             sai — progresso é preservado (imagens revisadas vão para captures/_reviewed/)

Uso:
    uv run python label_captures.py
    uv run python label_captures.py --dir captures
"""
import argparse
import os
import shutil
from pathlib import Path

# O Qt embutido no cv2 só traz o plugin "xcb" — em sessões Wayland ele tenta
# "wayland" por padrão e a janela fica sem receber clique nenhum. Força xcb
# (via XWayland) e desativa o auto-scaling de HiDPI do Qt, que também
# desalinha onde o clique é registrado.
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
os.environ.setdefault("QT_SCALE_FACTOR", "1")

import cv2

TEMPLATES_DIR = Path("templates")

# Tamanho máximo de janela na tela — screenshots em 2560x1440+ não cabem
# inteiros na maioria das telas. cv2.selectROI mapeia o ROI de volta para
# a resolução original da imagem, então o recorte salvo continua em
# resolução nativa mesmo com a janela exibida menor.
_MAX_WINDOW_W = 1600
_MAX_WINDOW_H = 900


def _show_resizable(window: str, frame) -> None:
    h, w = frame.shape[:2]
    scale = min(_MAX_WINDOW_W / w, _MAX_WINDOW_H / h, 1.0)
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, int(w * scale), int(h * scale))
    cv2.imshow(window, frame)


def _crop_and_save(frame, name: str) -> None:
    window = f"Recortar: {name}"
    _show_resizable(window, frame)
    roi = cv2.selectROI(window, frame, fromCenter=False, showCrosshair=True)
    cv2.destroyAllWindows()
    x, y, w, h = roi
    if w == 0 or h == 0:
        print("Cancelado (nenhuma região selecionada).")
        return

    cropped = frame[y:y + h, x:x + w]
    out_path = TEMPLATES_DIR / f"{name}.png"
    if out_path.exists():
        resp = input(f"  '{out_path}' já existe. Sobrescrever? [s/N] ").strip().lower()
        if resp != "s":
            print("  Não sobrescrito.")
            return

    cv2.imwrite(str(out_path), cropped)
    print(f"  Salvo: {out_path} ({w}x{h}px)")


def run(captures_dir: Path) -> None:
    TEMPLATES_DIR.mkdir(exist_ok=True)
    reviewed_dir = captures_dir / "_reviewed"
    reviewed_dir.mkdir(exist_ok=True, parents=True)

    images = sorted(p for p in captures_dir.glob("*.png") if p.parent == captures_dir)
    if not images:
        print(f"Nenhuma imagem em {captures_dir}/ (rode passive_capture.py primeiro).")
        return

    print(f"{len(images)} screenshot(s) para revisar.\n")

    for i, img_path in enumerate(images, 1):
        frame = cv2.imread(str(img_path))
        if frame is None:
            print(f"[{i}/{len(images)}] {img_path.name} — falha ao carregar, pulando.")
            continue

        window = "Preview — veja o terminal para opções"
        _show_resizable(window, frame)
        cv2.waitKey(1)

        print(f"\n[{i}/{len(images)}] {img_path.name}")
        action = input("  nome p/ recortar template | 'd' descarta | Enter pula | 'q' sai: ").strip()
        cv2.destroyWindow(window)

        if action.lower() == "q":
            print("\nSaindo — progresso preservado.")
            return

        if action.lower() == "d":
            img_path.unlink()
            print("  Descartado.")
            continue

        if action:
            _crop_and_save(frame, action)
            while input("  Recortar outro template nesta imagem? [s/N] ").strip().lower() == "s":
                name2 = input("  nome do template: ").strip()
                if name2:
                    _crop_and_save(frame, name2)

        shutil.move(str(img_path), str(reviewed_dir / img_path.name))

    print(f"\nRevisão concluída. Imagens processadas movidas para {reviewed_dir}/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Classificação manual de screenshots capturados.")
    parser.add_argument("--dir", default="captures", help="Diretório com screenshots capturados [captures]")
    args = parser.parse_args()
    run(Path(args.dir))


if __name__ == "__main__":
    main()
