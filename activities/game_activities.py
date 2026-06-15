"""
activities/game_activities.py

Activities do Temporal — cada uma é uma ação atômica no jogo.
O Temporal lida com retry automático, timeout e histórico de execução.

Convenção:
- Activities lançam exceções para erros recuperáveis (Temporal vai retry)
- Retornam False para estados "não encontrado" esperados (sem retry)
"""
import time
import logging
from temporalio import activity

from utils.vision import Vision
from utils import input as inp

logger = logging.getLogger(__name__)

# Instância compartilhada de visão (inicializada no worker)
_vision: Vision | None = None


def get_vision() -> Vision:
    global _vision
    if _vision is None:
        _vision = Vision(monitor_index=1, threshold=0.82)
    return _vision


# ---------------------------------------------------------------------------
# Activities: Gifts e Inventário
# ---------------------------------------------------------------------------

@activity.defn
async def collect_doggo_gift() -> bool:
    """
    Tenta coletar gift de Lizard Doggo.
    Retorna True se coletou, False se nenhum gift disponível.
    """
    v = get_vision()
    result = v.find("gift_prompt")

    if not result.found:
        logger.info("Nenhum gift disponível no momento (conf=%.2f)", result.confidence)
        return False

    logger.info("Gift encontrado em (%d, %d) — coletando...", result.x, result.y)
    inp.interact()

    confirm = v.wait_for("inventory_open", timeout=3.0)
    if confirm.found:
        time.sleep(0.3)
        inp.close_menu()
        logger.info("Gift coletado com sucesso.")
        return True

    raise RuntimeError("Menu de inventário não abriu após interagir com gift")


@activity.defn
async def check_inventory_full() -> bool:
    """Retorna True se o inventário está cheio (hora de ir craftar)."""
    v = get_vision()
    result = v.find("inventory_full_indicator", threshold=0.75)
    return result.found


@activity.defn
async def check_health_low() -> bool:
    """Retorna True se a vida está baixa."""
    v = get_vision()
    result = v.find("health_low_indicator", threshold=0.78)
    return result.found


# ---------------------------------------------------------------------------
# Activities: Craft de Munição
# ---------------------------------------------------------------------------

@activity.defn
async def navigate_to_equipment_workshop() -> bool:
    """
    Navega até o Equipment Workshop usando sequência de teclas.
    Adapte as durações para o layout da sua base.

    NOTA: Este é o candidato número 1 para falhar no início.
    Calibre as durações de movimento aqui primeiro.
    """
    logger.info("Navegando para o Equipment Workshop...")

    inp.move_forward(1.2)
    inp.strafe_right(0.8)
    inp.move_forward(0.5)

    v = get_vision()
    result = v.wait_for("equipment_workshop_prompt", timeout=5.0)
    if not result.found:
        raise RuntimeError("Não encontrou o Equipment Workshop após navegação")

    return True


@activity.defn
async def craft_rifle_ammo(quantity: int = 50) -> int:
    """Abre o Equipment Workshop e crafa munição de rifle. Retorna a quantidade craftada."""
    v = get_vision()

    inp.interact()
    if not v.wait_for("workshop_menu_open", timeout=4.0).found:
        raise RuntimeError("Menu do Workshop não abriu")

    ammo_icon = v.find("rifle_ammo_icon")
    if not ammo_icon.found:
        inp.close_menu()
        raise RuntimeError("Ícone de Rifle Ammo não encontrado no menu")

    inp.click(ammo_icon.x, ammo_icon.y)
    time.sleep(0.2)

    craft_btn = v.find("craft_button")
    if not craft_btn.found:
        inp.close_menu()
        raise RuntimeError("Botão de craft não encontrado")

    import pydirectinput
    pydirectinput.mouseDown(craft_btn.x, craft_btn.y)
    time.sleep(0.05 * quantity)
    pydirectinput.mouseUp(craft_btn.x, craft_btn.y)

    time.sleep(0.5)
    inp.close_menu()

    logger.info("Craftados ~%d rounds de Rifle Ammo", quantity)
    return quantity


@activity.defn
async def navigate_back_to_base() -> bool:
    """Retorna para a posição base após craftar."""
    inp.move_backward(1.2)
    inp.strafe_left(0.8)
    inp.move_backward(0.5)
    return True


# ---------------------------------------------------------------------------
# Activities: Combate e Loot
# ---------------------------------------------------------------------------

@activity.defn
async def scan_for_enemy() -> dict:
    """Escaneia a tela em busca de inimigos. Retorna dict com found, x, y, confidence."""
    v = get_vision()
    result = v.find_enemy()

    if result:
        logger.info("Inimigo detectado em (%d, %d) conf=%.2f", result.x, result.y, result.confidence)
        return {"found": True, "x": result.x, "y": result.y, "confidence": result.confidence}

    return {"found": False, "x": 0, "y": 0, "confidence": 0.0}


@activity.defn
async def engage_enemy(target_x: int, target_y: int, screen_w: int = 1920, screen_h: int = 1080) -> str:
    """
    Engaja um inimigo em target_x, target_y.
    Retorna: "killed", "escaped" ou "died"
    """
    v = get_vision()
    center_x, center_y = screen_w // 2, screen_h // 2

    logger.info("Engajando inimigo em (%d, %d)", target_x, target_y)

    inp.aim_at_screen_position(target_x, target_y, center_x, center_y, sensitivity_factor=0.8)
    time.sleep(0.1)

    combat_start = time.time()
    while time.time() - combat_start < 10.0:
        if await check_health_low():
            logger.warning("Vida baixa! Iniciando fuga.")
            inp.dodge("a")
            inp.move_backward(1.0)
            return "escaped"

        inp.shoot(bursts=5, interval=0.08)
        time.sleep(0.1)

        enemy = v.find_enemy()
        if not enemy:
            logger.info("Inimigo eliminado.")
            break

        inp.aim_at_screen_position(enemy.x, enemy.y, center_x, center_y, sensitivity_factor=0.8)

    if v.find("death_screen", threshold=0.90).found:
        logger.error("Personagem morreu durante combate!")
        return "died"

    time.sleep(0.8)
    remains = v.find("enemy_remains_prompt")
    if remains.found:
        inp.loot_remains()
        loot_confirm = v.wait_for("inventory_open", timeout=3.0)
        if loot_confirm.found:
            time.sleep(0.4)
            inp.close_menu()
            logger.info("Loot coletado com sucesso.")

    return "killed"


@activity.defn
async def handle_death_respawn() -> bool:
    """Lida com tela de morte — clica em respawn."""
    v = get_vision()
    respawn_btn = v.find("respawn_button", threshold=0.85)
    if respawn_btn.found:
        inp.click(respawn_btn.x, respawn_btn.y)
        logger.info("Clicou em respawn.")
        time.sleep(3.0)
        return True
    return False
