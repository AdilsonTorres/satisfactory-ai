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
    with screenshot_on_error("collect_doggo_gift"):
        v = get_vision()
        result = v.find("gift_prompt")

        if not result.found:
            logger.debug("Nenhum gift (conf=%.2f)", result.confidence)
            return False

        logger.info("Gift em (%d,%d) conf=%.2f — coletando.", result.x, result.y, result.confidence)
        inp.interact()

        confirm = v.wait_for("inventory_open", timeout=3.0)
        if confirm.found:
            time.sleep(0.3)
            inp.close_menu()
            logger.info("Gift coletado.")
            return True

        raise MenuError("Inventário não abriu após interagir com gift")


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
# Activities: Craft de Munição
# ---------------------------------------------------------------------------

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
        import pydirectinput
        pydirectinput.mouseDown(craft_btn.x, craft_btn.y)
        time.sleep(0.05 * quantity)
        pydirectinput.mouseUp(craft_btn.x, craft_btn.y)

        time.sleep(0.5)
        inp.close_menu()

        logger.info("Craftados ~%d Rifle Ammo.", quantity)
        return quantity


@activity.defn
async def navigate_back_to_base() -> bool:
    nav = cfg.get("navigation", {})
    inp.move_backward(nav.get("back_to_base_backward_1", 1.2))
    inp.strafe_left(nav.get("back_to_base_strafe_left", 0.8))
    inp.move_backward(nav.get("back_to_base_backward_2", 0.5))
    return True


# ---------------------------------------------------------------------------
# Activities: Combate e Loot
# ---------------------------------------------------------------------------

@activity.defn
async def scan_for_enemy() -> dict:
    v = get_vision()
    result = v.find_enemy()

    if result:
        logger.info(
            "Inimigo '%s' em (%d,%d) conf=%.2f",
            result.template_name, result.x, result.y, result.confidence
        )
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


# Resolução do import circular com Optional
from typing import Optional  # noqa: E402


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
