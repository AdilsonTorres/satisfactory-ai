"""
activities/game_activities.py

Activities do Temporal — ações atômicas no jogo.

Convenções:
- Exceções tipadas (VisionError, NavigationError, MenuError) aparecem
  de forma descritiva no histórico do Temporal.
- Activities longas chamam activity.heartbeat() periodicamente para
  evitar timeout falso do Temporal.
- screenshot_on_error: qualquer exceção não tratada salva screenshot
  automaticamente antes de propagar.
- BUG CORRIGIDO: check_health_low não era chamado como activity dentro
  de engage_enemy (não é possível chamar activity dentro de activity).
  Agora usa _check_health_inline() que acessa o Vision diretamente.
"""
import time
import logging
from contextlib import contextmanager
from typing import Optional
from temporalio import activity

from utils.vision import Vision
from utils.screenshot import save_debug_screenshot
from utils.exceptions import VisionError, NavigationError, MenuError, RespawnError
from utils import config as cfg
from utils import input as inp
from utils import stats as stats_module

logger = logging.getLogger(__name__)

_vision: Vision | None = None


def get_vision() -> Vision:
    global _vision
    if _vision is None:
        _vision = Vision()
    return _vision


@contextmanager
def screenshot_on_error(label: str):
    """Salva screenshot se a activity lançar exceção."""
    try:
        yield
    except Exception as exc:
        path = save_debug_screenshot(f"error_{label}")
        logger.error("[%s] %s: %s | screenshot: %s", label, type(exc).__name__, exc, path)
        raise


def _check_health_inline(v: Vision) -> bool:
    """
    Checa vida diretamente via Vision — sem dispatch Temporal.
    Usado dentro de engage_enemy (não é possível chamar outra activity
    de dentro de uma activity; usar o decorator seria chamar a função local,
    não uma nova execução do Temporal).
    """
    result = v.find("health_low_indicator")
    if result.found:
        logger.warning("Vida baixa detectada (conf=%.2f).", result.confidence)
    return result.found


# ---------------------------------------------------------------------------
# Activity: Screenshot
# ---------------------------------------------------------------------------

@activity.defn
async def take_debug_screenshot(label: str = "manual") -> str:
    """Tira screenshot imediato. Pode ser chamado de qualquer workflow."""
    path = save_debug_screenshot(label)
    logger.info("Screenshot: %s", path)
    return str(path)


# ---------------------------------------------------------------------------
# Activity: Persist Stats
# ---------------------------------------------------------------------------

@activity.defn
async def persist_session_stats(workflow_type: str, stats: dict) -> str:
    """Salva estatísticas de sessão em stats/ ao final do workflow."""
    path = stats_module.save(workflow_type, stats)
    logger.info("Estatísticas salvas: %s", path)
    return str(path)


# ---------------------------------------------------------------------------
# Activities: Gifts e Inventário
# ---------------------------------------------------------------------------

@activity.defn
async def collect_doggo_gift() -> bool:
    """
    Interagir com um Lizard Doggo abre a janela de loot de UM slot do próprio
    Doggo — não o inventário do jogador. Aguardamos 'doggo_loot_window'
    (não 'inventory_open'). Doggos sem item têm só ~0.2%/s de chance de
    achar algo (~8min de média), então a maioria das interações vai
    encontrar a janela vazia — isso é esperado, não é falha.
    """
    with screenshot_on_error("collect_doggo_gift"):
        v = get_vision()
        result = v.find("gift_prompt")

        if not result.found:
            logger.debug("Nenhum gift (conf=%.2f)", result.confidence)
            return False

        logger.info("Gift em (%d,%d) conf=%.2f — coletando.", result.x, result.y, result.confidence)
        inp.interact()

        confirm = v.wait_for("doggo_loot_window", timeout=3.0)
        if confirm.found:
            time.sleep(0.3)
            inp.close_menu()
            logger.info("Gift coletado.")
            return True

        raise MenuError("Janela de loot do Doggo não abriu após interagir")


@activity.defn
async def check_inventory_full() -> bool:
    v = get_vision()
    result = v.find("inventory_full_indicator")
    logger.debug("Inventário cheio: %s (conf=%.2f)", result.found, result.confidence)
    return result.found


@activity.defn
async def check_health_low() -> bool:
    """Checa vida baixa. Quando chamado de um workflow, usa dispatch Temporal normal."""
    return _check_health_inline(get_vision())


# ---------------------------------------------------------------------------
# Activities: Domesticação de Lizard Doggo
# ---------------------------------------------------------------------------

@activity.defn
async def feed_wild_doggo() -> bool:
    """
    Tenta domesticar um Lizard Doggo selvagem: abre o inventário, arrasta uma
    Paleberry para um ponto fixo da tela (queda no mundo, perto do jogador) e
    fecha o inventário.

    A confirmação de sucesso (Doggo come, pula e "chia") é um cue visual fraco
    e não é verificada aqui — best-effort. Doggos competem pela mesma berry,
    por isso o workflow chama esta activity várias vezes.
    """
    with screenshot_on_error("feed_wild_doggo"):
        v = get_vision()
        wild = v.find("wild_doggo_prompt")
        if not wild.found:
            logger.debug("Nenhum Doggo selvagem à vista (conf=%.2f)", wild.confidence)
            return False

        inp.open_inventory()
        berry = v.wait_for("paleberry_icon", timeout=2.0)
        if not berry.found:
            inp.close_menu()
            raise VisionError(
                "paleberry_icon", berry.confidence,
                cfg.get("vision.thresholds.paleberry_icon", 0.85)
            )

        taming = cfg.get("taming", {})
        drop_x = taming.get("drop_point_x", 1280)
        drop_y = taming.get("drop_point_y", 720)
        inp.drag(berry.x, berry.y, drop_x, drop_y)
        time.sleep(0.3)
        inp.close_menu()

        logger.info("Paleberry oferecida ao Doggo selvagem (conf=%.2f).", wild.confidence)
        return True


# ---------------------------------------------------------------------------
# Activities: Craft de Munição
# ---------------------------------------------------------------------------

@activity.defn
async def navigate_to_location(location: str) -> bool:
    """
    Navega até um local nomeado em config.toml [locations.<location>]:
    executa a sequência fixa de tecla/duração (steps) e, se o local tiver
    'arrival_template', confirma a chegada por visão.

    Generaliza o padrão usado por navigate_to_equipment_workshop para locais
    arbitrários (zonas de combate, storage, etc.) sem precisar de uma
    activity dedicada para cada um.
    """
    with screenshot_on_error(f"navigate_to_{location}"):
        loc = cfg.get(f"locations.{location}")
        if not loc:
            raise NavigationError(
                f"Local '{location}' não definido em config.toml [locations.{location}]."
            )

        steps = loc.get("steps", [])
        logger.info("Navegando para '%s' (%d passo(s))...", location, len(steps))
        for i, step in enumerate(steps):
            activity.heartbeat(f"passo {i + 1}/{len(steps)} de '{location}'")
            inp.hold(step["key"], step.get("duration", 0.5))

        arrival_template = loc.get("arrival_template")
        if arrival_template:
            v = get_vision()
            result = v.wait_for(arrival_template, timeout=loc.get("arrival_timeout", 5.0))
            if not result.found:
                raise NavigationError(
                    f"Chegada em '{location}' não confirmada — template "
                    f"'{arrival_template}' não encontrado. Ajuste [locations.{location}] em config.toml."
                )

        logger.info("Chegada em '%s' concluída.", location)
        return True


@activity.defn
async def navigate_to_equipment_workshop() -> bool:
    """
    Navega até o Equipment Workshop via sequência de teclas configurada em config.toml.
    Se falhar, ajuste [navigation] no config.toml.
    """
    with screenshot_on_error("navigate_to_workshop"):
        nav = cfg.get("navigation", {})
        logger.info("Navegando para o Equipment Workshop...")
        activity.heartbeat("iniciando navegação")

        inp.move_forward(nav.get("to_workshop_forward_1", 1.2))
        activity.heartbeat("andando para frente (1)")
        inp.strafe_right(nav.get("to_workshop_strafe_right", 0.8))
        inp.move_forward(nav.get("to_workshop_forward_2", 0.5))

        v = get_vision()
        result = v.wait_for("equipment_workshop_prompt", timeout=5.0)
        if not result.found:
            raise NavigationError(
                "Equipment Workshop não encontrado após navegação. "
                "Ajuste [navigation] em config.toml."
            )

        logger.info("Workshop em (%d,%d).", result.x, result.y)
        return True


@activity.defn
async def check_ammo_count() -> int:
    """
    Lê a contagem de munição do HUD via OCR (região configurável em
    config.toml [combat.ammo_region]). Retorna -1 se a leitura falhar ou a
    região não estiver calibrada — o workflow trata -1 como "desconhecido"
    e não bloqueia o combate por isso.
    """
    v = get_vision()
    region = cfg.get("combat.ammo_region", {})
    text = v.read_text_region(
        region.get("x", 0), region.get("y", 0),
        region.get("w", 80), region.get("h", 40),
    )
    try:
        count = int(text)
        logger.debug("Munição detectada: %d", count)
        return count
    except ValueError:
        logger.warning("Falha ao ler contagem de munição (OCR retornou '%s').", text)
        return -1


@activity.defn
async def craft_rifle_ammo(quantity: int = 50) -> int:
    with screenshot_on_error("craft_rifle_ammo"):
        v = get_vision()

        inp.interact()
        activity.heartbeat("aguardando menu do workshop")
        if not v.wait_for("workshop_menu_open", timeout=4.0).found:
            raise MenuError("Menu do Workshop não abriu")

        ammo_icon = v.find("rifle_ammo_icon")
        if not ammo_icon.found:
            inp.close_menu()
            r = ammo_icon
            raise VisionError("rifle_ammo_icon", r.confidence,
                               cfg.get("vision.thresholds.rifle_ammo_icon", 0.85))

        inp.click(ammo_icon.x, ammo_icon.y)
        time.sleep(0.2)

        craft_btn = v.find("craft_button")
        if not craft_btn.found:
            inp.close_menu()
            raise VisionError("craft_button", craft_btn.confidence,
                               cfg.get("vision.thresholds.craft_button", 0.87))

        activity.heartbeat(f"craftando {quantity} unidades")
        from pynput.mouse import Controller as _MC, Button as _Btn
        _m = _MC()
        _m.position = (craft_btn.x, craft_btn.y)
        _m.press(_Btn.left)
        time.sleep(0.05 * quantity)
        _m.release(_Btn.left)

        time.sleep(0.5)
        inp.close_menu()

        logger.info("Craftados ~%d Rifle Ammo.", quantity)
        return quantity


@activity.defn
async def harvest_resource_node(swings: int = 20) -> int:
    """
    Colhe um node de recurso (picareta manual ou node já desbloqueado por
    Nobelisk) pressionando interagir repetidamente. Assume que o jogador já
    está posicionado dentro do alcance — não há navegação até o node;
    esse posicionamento é feito manualmente uma vez, como no Workshop.
    """
    with screenshot_on_error("harvest_resource_node"):
        v = get_vision()
        check = v.find("resource_node_prompt")
        if not check.found:
            raise VisionError(
                "resource_node_prompt", check.confidence,
                cfg.get("vision.thresholds.resource_node_prompt", 0.80)
            )

        interval = cfg.get("harvesting.swing_interval_seconds", 0.5)
        count = 0
        for i in range(swings):
            activity.heartbeat(f"colhendo {i + 1}/{swings}")
            inp.interact()
            time.sleep(interval)
            count += 1

        logger.info("Colheita concluída: %d interações no node.", count)
        return count


@activity.defn
async def open_storage_and_deposit_loot() -> int:
    """
    Abre um storage container (precisa ter o prompt de interação no alcance)
    e percorre o grid de inventário do jogador com shift-click em cada slot
    para transferir tudo de uma vez. Shift-click num slot vazio não faz
    nada, então é seguro varrer o grid inteiro sem detectar item por item.

    Best-effort: confirma que o storage abriu, mas não verifica se os itens
    realmente foram transferidos. Calibre [inventory_grid] em config.toml
    com as coordenadas reais do seu layout de inventário/resolução.
    """
    with screenshot_on_error("open_storage_and_deposit_loot"):
        v = get_vision()
        prompt = v.find("storage_prompt")
        if not prompt.found:
            raise VisionError(
                "storage_prompt", prompt.confidence,
                cfg.get("vision.thresholds.storage_prompt", 0.82)
            )

        inp.interact()
        opened = v.wait_for("storage_open", timeout=3.0)
        if not opened.found:
            raise MenuError("Janela de storage não abriu após interagir")

        grid = cfg.get("inventory_grid", {})
        origin_x = grid.get("origin_x", 100)
        origin_y = grid.get("origin_y", 100)
        slot_w = grid.get("slot_w", 90)
        slot_h = grid.get("slot_h", 90)
        columns = grid.get("columns", 10)
        rows = grid.get("rows", 4)

        slots_clicked = 0
        for row in range(rows):
            activity.heartbeat(f"linha {row + 1}/{rows} do inventário")
            for col in range(columns):
                inp.shift_click(origin_x + col * slot_w, origin_y + row * slot_h)
                slots_clicked += 1

        time.sleep(0.3)
        inp.close_menu()
        logger.info("Storage: %d slot(s) varrido(s) com shift-click.", slots_clicked)
        return slots_clicked


@activity.defn
async def navigate_back_to_base() -> bool:
    """
    Retorna ao ponto de farm. Verifica que o personagem realmente saiu da
    área do Workshop (se o prompt ainda estiver visível, a movimentação
    não surtiu efeito — colisão, obstrução, etc).
    """
    with screenshot_on_error("navigate_back_to_base"):
        nav = cfg.get("navigation", {})
        inp.move_backward(nav.get("back_to_base_backward_1", 1.2))
        inp.strafe_left(nav.get("back_to_base_strafe_left", 0.8))
        inp.move_backward(nav.get("back_to_base_backward_2", 0.5))

        v = get_vision()
        if v.find("equipment_workshop_prompt").found:
            raise NavigationError(
                "Ainda dentro da área do Equipment Workshop após navegar de volta. "
                "Personagem pode estar obstruído. Ajuste [navigation] em config.toml."
            )
        return True


# ---------------------------------------------------------------------------
# Activities: Combate e Loot
# ---------------------------------------------------------------------------

# Variantes que causam dano em área (radiação/gás) — o loop estático de
# aim-and-shoot do engage_enemy não foi desenhado para isso. Workflows devem
# tratar "hazard" como sinal para recuar em vez de engajar normalmente.
HAZARD_ENEMY_TYPES = {"enemy_hog_nuclear", "enemy_stinger_elite_gas"}


@activity.defn
async def scan_for_enemy() -> dict:
    v = get_vision()
    result = v.find_enemy()

    if result:
        hazard = result.template_name in HAZARD_ENEMY_TYPES
        logger.info(
            "Inimigo '%s' em (%d,%d) conf=%.2f hazard=%s",
            result.template_name, result.x, result.y, result.confidence, hazard
        )
        return {
            "found": True,
            "x": result.x,
            "y": result.y,
            "confidence": result.confidence,
            "type": result.template_name,
            "hazard": hazard,
        }

    return {"found": False, "x": 0, "y": 0, "confidence": 0.0, "type": "", "hazard": False}


@activity.defn
async def retreat_from_hazard() -> bool:
    """
    Recua sem engajar — usado quando scan_for_enemy sinaliza 'hazard'
    (variante com dano em área de radiação/gás). O loop estático de
    aim-and-shoot do engage_enemy não é seguro contra essas variantes.
    """
    inp.move_backward(1.5)
    inp.dodge()
    logger.warning("Recuando de inimigo hazard (dano em área) sem engajar.")
    return True


@activity.defn
async def engage_enemy(
    target_x: int,
    target_y: int,
    screen_w: Optional[int] = None,
    screen_h: Optional[int] = None,
) -> str:
    """
    Engaja inimigo em (target_x, target_y).
    Parâmetros de combate veem de config.toml[combat].
    Retorna: 'killed' | 'escaped' | 'died'
    """
    with screenshot_on_error("engage_enemy"):
        v = get_vision()
        disp = cfg.get("display", {})
        sw = screen_w or disp.get("screen_width", 1920)
        sh = screen_h or disp.get("screen_height", 1080)
        center_x, center_y = sw // 2, sh // 2
        max_dur = cfg.get("combat.max_combat_duration_seconds", 10.0)

        logger.info("Engajando inimigo em (%d,%d)", target_x, target_y)
        inp.aim_at_screen_position(target_x, target_y, center_x, center_y)
        time.sleep(0.1)

        combat_start = time.time()
        bursts_fired = 0

        while time.time() - combat_start < max_dur:
            activity.heartbeat(f"combate — {bursts_fired} bursts")

            # _check_health_inline evita chamar outra activity de dentro de activity
            if _check_health_inline(v):
                logger.warning("Vida baixa — fugindo.")
                inp.dodge()
                inp.move_backward(1.0)
                return "escaped"

            inp.shoot()
            bursts_fired += 1
            time.sleep(0.1)

            enemy = v.find_enemy()
            if not enemy:
                logger.info("Inimigo eliminado após %d bursts.", bursts_fired)
                break

            inp.aim_at_screen_position(enemy.x, enemy.y, center_x, center_y)

        if v.find("death_screen").found:
            save_debug_screenshot("player_death")
            logger.error("Personagem morreu durante combate.")
            return "died"

        time.sleep(0.8)
        remains = v.find("enemy_remains_prompt")
        if remains.found:
            inp.loot_remains()
            if v.wait_for("inventory_open", timeout=3.0).found:
                time.sleep(0.4)
                inp.close_menu()
                logger.info("Loot coletado.")

        return "killed"


@activity.defn
async def handle_death_respawn() -> bool:
    with screenshot_on_error("handle_death_respawn"):
        v = get_vision()
        btn = v.find("respawn_button")
        if btn.found:
            inp.click(btn.x, btn.y)
            logger.info("Clicou em respawn.")
            time.sleep(3.0)
            return True

        save_debug_screenshot("respawn_not_found")
        raise RespawnError(
            f"Botão de respawn não encontrado (conf={btn.confidence:.3f}). "
            "Verifique se o template 'respawn_button.png' está correto."
        )


@activity.defn
async def capture_template_screen(screen_name: str, key_to_open: str = "", key_to_close: str = "") -> str:
    """Foca o jogo, envia comando para abrir, captura a tela e fecha o menu."""
    import time
    from utils.screenshot import save_debug_screenshot
    
    inp.focus_game("Satisfactory")
    time.sleep(0.5)
    
    if key_to_open:
        inp.press(key_to_open)
        time.sleep(0.8) # Aguarda animação de abertura
            
    v = get_vision()
    frame = v.capture()
    path = save_debug_screenshot(screen_name, frame=frame)
    logger.info("Tela capturada para calibração: %s", path)
    
    if key_to_close:
        inp.press(key_to_close)
        time.sleep(0.3)
        
    return str(path)


@activity.defn
async def extract_templates_from_screen(screenshot_path: str, target: str = "hud", resolution: str = "2560x1440") -> dict:
    """Extrai regiões de interesse da captura e salva como novos templates PNG."""
    import cv2
    from pathlib import Path
    
    path = Path(screenshot_path)
    if not path.exists():
        raise FileNotFoundError(f"Captura não encontrada: {screenshot_path}")
        
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"Falha ao carregar imagem: {screenshot_path}")
        
    h, w = img.shape[:2]
    logger.info("Extraindo templates para alvo '%s' e resolução %dx%d (config: %s)", target, w, h, resolution)
    
    templates_dir = Path("templates")
    templates_dir.mkdir(exist_ok=True)
    
    results = {}
    
    # Coordenadas mapeadas para 2560x1440 e fallback proporcional
    if target == "hud":
        if w == 2560 and h == 1440:
            coords = {
                "health_low_indicator": (1330, 1380, 70, 120),  # Ícone do coração (vida)
                "inventory_open": (1215, 1265, 2185, 2245),       # Ícone do Tab no HUD
            }
        else:
            coords = {
                "health_low_indicator": (int(h * 0.923), int(h * 0.958), int(w * 0.027), int(w * 0.047)),
                "inventory_open": (int(h * 0.843), int(h * 0.878), int(w * 0.853), int(w * 0.877)),
            }
    elif target == "workshop":
        # Nota: Coordenadas temporárias de calibração para o Equipment Workshop em 2560x1440
        if w == 2560 and h == 1440:
            coords = {
                "workshop_menu_open": (50, 150, 100, 400),      # Título do menu Workshop (topo esquerdo)
                "rifle_ammo_icon": (400, 600, 300, 500),        # Ícone de munição de rifle no menu
                "craft_button": (1000, 1200, 1800, 2200),       # Botão de craft (segurar para fabricar)
            }
        else:
            coords = {
                "workshop_menu_open": (int(h * 0.034), int(h * 0.104), int(w * 0.039), int(w * 0.156)),
                "rifle_ammo_icon": (int(h * 0.277), int(h * 0.416), int(w * 0.117), int(w * 0.195)),
                "craft_button": (int(h * 0.694), int(h * 0.833), int(w * 0.703), int(w * 0.859)),
            }
    else:
        raise ValueError(f"Alvo desconhecido para extração: {target}")
        
    for name, (y1, y2, x1, x2) in coords.items():
        cropped = img[y1:y2, x1:x2]
        out_path = templates_dir / f"{name}.png"
        cv2.imwrite(str(out_path), cropped)
        results[name] = str(out_path)
        logger.info("Template '%s' extraído e salvo em %s", name, out_path)
        
    return results


@activity.defn
async def reset_to_safe_state() -> bool:
    """
    Limpeza defensiva: fecha qualquer menu aberto (gift, inventário, workshop).
    Chamada ao cancelar/encerrar um workflow para não deixar o jogo com um
    menu aberto entre uma sessão e a próxima.
    """
    inp.close_menu()
    time.sleep(0.2)
    inp.close_menu()
    logger.info("Estado seguro restaurado (menus fechados).")
    return True


@activity.defn
async def verify_matching_templates(template_names: list[str]) -> dict:
    """Escaneia a tela atual buscando os templates e retorna o status de confiança."""
    v = get_vision()
    results = v.scan_all(template_names)
    
    report = {}
    for name, r in results.items():
        report[name] = {
            "found": r.found,
            "x": r.x,
            "y": r.y,
            "confidence": float(r.confidence),
        }
        logger.info("Verificação de '%s': found=%s, conf=%.3f", name, r.found, r.confidence)
    return report
