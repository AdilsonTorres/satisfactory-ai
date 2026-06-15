"""
activities/game_activities.py

Activities do Temporal — cada uma é uma ação atômica no jogo.

Convenção:
- Activities lançam exceções para erros recuperáveis (Temporal vai retry)
- Retornam False/None para estados esperados de "não encontrado" (sem retry)
- Activities longas chamam activity.heartbeat() para evitar timeout do Temporal
- Em qualquer exceção não tratada, um screenshot é salvo automaticamente em debug_screenshots/
"""
import time
import logging
from contextlib import contextmanager
from temporalio import activity

from utils.vision import Vision
from utils.screenshot import save_debug_screenshot
from utils import input as inp

logger = logging.getLogger(__name__)

_vision: Vision | None = None


def get_vision() -> Vision:
    global _vision
    if _vision is None:
        _vision = Vision(monitor_index=1, threshold=0.82)
    return _vision


@contextmanager
def screenshot_on_error(label: str):
    """
    Salva screenshot automaticamente se a activity lançar uma exceção.
    Inclui o nome da activity e o erro no nome do arquivo.
    """
    try:
        yield
    except Exception as exc:
        path = save_debug_screenshot(f"error_{label}")
        logger.error("[%s] Erro: %s | Screenshot: %s", label, exc, path)
        raise


# ---------------------------------------------------------------------------
# Activity: Debug Screenshot
# ---------------------------------------------------------------------------

@activity.defn
async def take_debug_screenshot(label: str = "manual") -> str:
    """
    Tira um screenshot imediato e salva em debug_screenshots/.
    Pode ser chamado a qualquer momento a partir de um workflow.
    Retorna o caminho do arquivo salvo.
    """
    path = save_debug_screenshot(label)
    logger.info("Screenshot salvo: %s", path)
    return str(path)


# ---------------------------------------------------------------------------
# Activities: Gifts e Inventário
# ---------------------------------------------------------------------------

@activity.defn
async def collect_doggo_gift() -> bool:
    """
    Tenta coletar gift de Lizard Doggo.
    Retorna True se coletou, False se nenhum gift disponível.
    """
    with screenshot_on_error("collect_doggo_gift"):
        v = get_vision()
        result = v.find("gift_prompt")

        if not result.found:
            logger.debug("Nenhum gift (conf=%.2f)", result.confidence)
            return False

        logger.info("Gift encontrado em (%d, %d) conf=%.2f", result.x, result.y, result.confidence)
        inp.interact()

        confirm = v.wait_for("inventory_open", timeout=3.0)
        if confirm.found:
            time.sleep(0.3)
            inp.close_menu()
            logger.info("Gift coletado.")
            return True

        raise RuntimeError("Menu de inventário não abriu após interagir com gift")


@activity.defn
async def check_inventory_full() -> bool:
    v = get_vision()
    result = v.find("inventory_full_indicator", threshold=0.75)
    logger.debug("Inventário cheio: %s (conf=%.2f)", result.found, result.confidence)
    return result.found


@activity.defn
async def check_health_low() -> bool:
    v = get_vision()
    result = v.find("health_low_indicator", threshold=0.78)
    if result.found:
        logger.warning("Vida baixa detectada (conf=%.2f)", result.confidence)
    return result.found


# ---------------------------------------------------------------------------
# Activities: Craft de Munição
# ---------------------------------------------------------------------------

@activity.defn
async def navigate_to_equipment_workshop() -> bool:
    """
    Navega até o Equipment Workshop usando sequência de teclas.
    Adapte as durações para o layout da sua base.
    ESTE É O PONTO MAIS COMUM DE FALHA — calibre aqui primeiro.
    """
    with screenshot_on_error("navigate_to_workshop"):
        logger.info("Navegando para o Equipment Workshop...")
        activity.heartbeat("iniciando navegação")

        inp.move_forward(1.2)
        activity.heartbeat("andando para frente")
        inp.strafe_right(0.8)
        inp.move_forward(0.5)

        v = get_vision()
        result = v.wait_for("equipment_workshop_prompt", timeout=5.0)
        if not result.found:
            raise RuntimeError(
                "Equipment Workshop não encontrado após navegação. "
                "Verifique o template e as durações de movimento em utils/input.py"
            )

        logger.info("Workshop encontrado em (%d, %d)", result.x, result.y)
        return True


@activity.defn
async def craft_rifle_ammo(quantity: int = 50) -> int:
    """Abre o Equipment Workshop e crafa munição de rifle."""
    with screenshot_on_error("craft_rifle_ammo"):
        v = get_vision()

        inp.interact()
        activity.heartbeat("aguardando menu do workshop")
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

        activity.heartbeat(f"craftando {quantity} unidades")
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
    inp.move_backward(1.2)
    inp.strafe_left(0.8)
    inp.move_backward(0.5)
    return True


# ---------------------------------------------------------------------------
# Activities: Combate e Loot
# ---------------------------------------------------------------------------

@activity.defn
async def scan_for_enemy() -> dict:
    """Escaneia a tela em busca de inimigos conhecidos."""
    v = get_vision()
    result = v.find_enemy()

    if result:
        logger.info("Inimigo detectado: %s em (%d, %d) conf=%.2f",
                    result.template_name, result.x, result.y, result.confidence)
        return {
            "found": True,
            "x": result.x,
            "y": result.y,
            "confidence": result.confidence,
            "type": result.template_name,
        }

    return {"found": False, "x": 0, "y": 0, "confidence": 0.0, "type": ""}


@activity.defn
async def engage_enemy(
    target_x: int,
    target_y: int,
    screen_w: int = 1920,
    screen_h: int = 1080,
) -> str:
    """
    Engaja um inimigo em (target_x, target_y).
    Retorna: "killed" | "escaped" | "died"
    """
    with screenshot_on_error("engage_enemy"):
        v = get_vision()
        center_x, center_y = screen_w // 2, screen_h // 2

        logger.info("Engajando inimigo em (%d, %d)", target_x, target_y)
        inp.aim_at_screen_position(target_x, target_y, center_x, center_y, sensitivity_factor=0.8)
        time.sleep(0.1)

        combat_start = time.time()
        shots_fired = 0

        while time.time() - combat_start < 10.0:
            activity.heartbeat(f"em combate — {shots_fired} bursts disparados")

            if await check_health_low():
                logger.warning("Vida baixa — fugindo.")
                inp.dodge("a")
                inp.move_backward(1.0)
                return "escaped"

            inp.shoot(bursts=5, interval=0.08)
            shots_fired += 5
            time.sleep(0.1)

            enemy = v.find_enemy()
            if not enemy:
                logger.info("Inimigo eliminado após %d bursts.", shots_fired)
                break

            inp.aim_at_screen_position(enemy.x, enemy.y, center_x, center_y, sensitivity_factor=0.8)

        if v.find("death_screen", threshold=0.90).found:
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
    """Detecta tela de morte e clica em respawn."""
    with screenshot_on_error("handle_death_respawn"):
        v = get_vision()
        respawn_btn = v.find("respawn_button", threshold=0.85)
        if respawn_btn.found:
            inp.click(respawn_btn.x, respawn_btn.y)
            logger.info("Clicou em respawn.")
            time.sleep(3.0)
            return True

        save_debug_screenshot("respawn_not_found")
        logger.error("Botão de respawn não encontrado na tela.")
        return False
