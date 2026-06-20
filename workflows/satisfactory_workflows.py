"""
workflows/satisfactory_workflows.py

Workflows com:
- Signals: pause / resume / stop
- Queries: get_stats
- Screenshots periódicos configuráveis
- Estatísticas persistidas em JSON ao final (via persist_session_stats activity)

Controle via CLI:
    temporal workflow signal --workflow-id <id> --name pause
    temporal workflow signal --workflow-id <id> --name resume
    temporal workflow signal --workflow-id <id> --name stop
    temporal workflow query  --workflow-id <id> --query-type get_stats
"""
import asyncio
import logging
from datetime import timedelta
from typing import Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities.game_activities import (
        collect_doggo_gift,
        check_inventory_full,
        check_health_low,
        feed_wild_doggo,
        navigate_to_equipment_workshop,
        craft_rifle_ammo,
        navigate_back_to_base,
        harvest_resource_node,
        scan_for_enemy,
        engage_enemy,
        retreat_from_hazard,
        handle_death_respawn,
        take_debug_screenshot,
        persist_session_stats,
        capture_template_screen,
        extract_templates_from_screen,
        verify_matching_templates,
        reset_to_safe_state,
        navigate_to_location,
        check_ammo_count,
        open_storage_and_deposit_loot,
    )

logger = logging.getLogger(__name__)

GAME_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_attempts=3,
    backoff_coefficient=2.0,
    # FileNotFoundError = template faltando = bug, não retry
    # NavigationError after max_attempts = aborta o workflow
    non_retryable_error_types=["FileNotFoundError"],
)

NAV_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    maximum_attempts=5,
    backoff_coefficient=1.5,
)

NO_RETRY = RetryPolicy(maximum_attempts=1)

_SS_TIMEOUT = timedelta(seconds=10)
_SS_RETRY   = RetryPolicy(maximum_attempts=1)


async def _screenshot(label: str) -> None:
    await workflow.execute_activity(
        take_debug_screenshot,
        args=[label],
        schedule_to_close_timeout=_SS_TIMEOUT,
        retry_policy=_SS_RETRY,
    )


async def _save_stats(workflow_type: str, stats: dict) -> None:
    await workflow.execute_activity(
        persist_session_stats,
        args=[workflow_type, stats],
        schedule_to_close_timeout=timedelta(seconds=15),
        retry_policy=RetryPolicy(maximum_attempts=2),
    )


async def _cleanup_on_cancel(workflow_type: str) -> None:
    """Fecha menus abertos no jogo antes de deixar a exceção de cancelamento propagar."""
    try:
        await workflow.execute_activity(
            reset_to_safe_state,
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
    except Exception as exc:
        workflow.logger.error("Limpeza de cancelamento de %s falhou: %s", workflow_type, exc)


# NAV_RETRY permite 5 tentativas com backoff (2s, 3s, 4.5s, 6.75s ~= 16.25s de espera).
# schedule_to_close_timeout precisa cobrir esse backoff + o tempo de execução de
# todas as tentativas, não apenas uma — por isso é maior que start_to_close_timeout.
async def _run_craft_cycle(ammo_per_craft: int) -> None:
    await workflow.execute_activity(
        navigate_to_equipment_workshop,
        start_to_close_timeout=timedelta(seconds=10),
        schedule_to_close_timeout=timedelta(seconds=70),
        heartbeat_timeout=timedelta(seconds=8),
        retry_policy=NAV_RETRY,
    )
    await workflow.execute_activity(
        craft_rifle_ammo,
        args=[ammo_per_craft],
        start_to_close_timeout=timedelta(seconds=15),
        schedule_to_close_timeout=timedelta(seconds=60),
        heartbeat_timeout=timedelta(seconds=8),
        retry_policy=GAME_RETRY,
    )
    await workflow.execute_activity(
        navigate_back_to_base,
        start_to_close_timeout=timedelta(seconds=8),
        schedule_to_close_timeout=timedelta(seconds=60),
        retry_policy=NAV_RETRY,
    )


# ---------------------------------------------------------------------------
# Mixin de controle (pause / resume / stop / get_stats)
# ---------------------------------------------------------------------------

class _ControlMixin:
    """Signals e query compartilhados por todos os workflows."""

    def __init__(self) -> None:
        self._paused = False
        self._stop_requested = False
        self._stats: dict = {"status": "running"}

    @workflow.signal
    async def pause(self) -> None:
        self._paused = True
        self._stats["status"] = "paused"
        workflow.logger.info("Pausado.")

    @workflow.signal
    async def resume(self) -> None:
        self._paused = False
        self._stats["status"] = "running"
        workflow.logger.info("Retomado.")

    @workflow.signal
    async def stop(self) -> None:
        self._stop_requested = True
        self._paused = False
        self._stats["status"] = "stopping"
        workflow.logger.info("Encerramento solicitado.")

    @workflow.query
    def get_stats(self) -> dict:
        return self._stats

    async def _wait_if_paused(self) -> None:
        while self._paused and not self._stop_requested:
            await workflow.sleep(timedelta(seconds=1))


# ---------------------------------------------------------------------------
# Workflow: AFK Gift Farm
# ---------------------------------------------------------------------------

@workflow.defn
class GiftFarmWorkflow(_ControlMixin):
    """
    Loop de AFK farm de gifts dos Lizard Doggos.

    Parâmetros:
        ammo_per_craft (int):           Rifle Ammo por ciclo de craft [50]
        screenshot_every_cycles (int):  Screenshot a cada N ciclos [10]

    Query get_stats retorna:
        {gifts, ammo_crafted, cycles, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {"gifts": 0, "ammo_crafted": 0, "cycles": 0, "status": "running"}

    @workflow.run
    async def run(
        self,
        ammo_per_craft: int = 50,
        screenshot_every_cycles: int = 10,
        _resume_stats: Optional[dict] = None,
    ) -> dict:
        if _resume_stats is not None:
            self._stats = _resume_stats
        workflow.logger.info("GiftFarmWorkflow iniciado.")

        try:
            while not self._stop_requested:
                await self._wait_if_paused()
                if self._stop_requested:
                    break

                if workflow.info().is_continue_as_new_suggested():
                    workflow.logger.info("Histórico extenso — continuando como novo workflow.")
                    workflow.continue_as_new(args=[ammo_per_craft, screenshot_every_cycles, self._stats])

                self._stats["cycles"] += 1
                cycle = self._stats["cycles"]
                workflow.logger.info(
                    "Ciclo #%d | gifts=%d ammo=%d",
                    cycle, self._stats["gifts"], self._stats["ammo_crafted"]
                )

                if screenshot_every_cycles > 0 and cycle % screenshot_every_cycles == 0:
                    await _screenshot(f"gift_cycle_{cycle}")

                collected = await workflow.execute_activity(
                    collect_doggo_gift,
                    schedule_to_close_timeout=timedelta(seconds=15),
                    retry_policy=GAME_RETRY,
                )
                if collected:
                    self._stats["gifts"] += 1

                inv_full = await workflow.execute_activity(
                    check_inventory_full,
                    schedule_to_close_timeout=timedelta(seconds=5),
                    retry_policy=GAME_RETRY,
                )
                if inv_full:
                    await _screenshot(f"inv_full_{cycle}")
                    await _run_craft_cycle(ammo_per_craft)
                    self._stats["ammo_crafted"] += ammo_per_craft

                await workflow.sleep(timedelta(seconds=3))

            self._stats["status"] = "stopped"
            await _save_stats("GiftFarmWorkflow", self._stats)
            return self._stats
        except asyncio.CancelledError:
            workflow.logger.warning("GiftFarmWorkflow cancelado — limpando estado do jogo.")
            await asyncio.shield(_cleanup_on_cancel("GiftFarmWorkflow"))
            raise


# ---------------------------------------------------------------------------
# Workflow: Patrulha de Combate
# ---------------------------------------------------------------------------

@workflow.defn
class CombatPatrolWorkflow(_ControlMixin):
    """
    Patrulha estática: fica no lugar e reage a inimigos que entram no campo de visão.

    Parâmetros:
        max_kills (int):               Kills para encerrar [20]
        screenshot_every_kills (int):  Screenshot a cada N kills [5]

    Query get_stats retorna:
        {kills, deaths, escaped, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {"kills": 0, "deaths": 0, "escaped": 0, "status": "running"}

    @workflow.run
    async def run(
        self,
        max_kills: int = 20,
        screenshot_every_kills: int = 5,
        _resume_stats: Optional[dict] = None,
    ) -> dict:
        if _resume_stats is not None:
            self._stats = _resume_stats
        workflow.logger.info("CombatPatrolWorkflow iniciado. max_kills=%d", max_kills)

        try:
            return await self._run_patrol(max_kills, screenshot_every_kills)
        except asyncio.CancelledError:
            workflow.logger.warning("CombatPatrolWorkflow cancelado — limpando estado do jogo.")
            await asyncio.shield(_cleanup_on_cancel("CombatPatrolWorkflow"))
            raise

    async def _run_patrol(self, max_kills: int, screenshot_every_kills: int) -> dict:
        while self._stats["kills"] < max_kills and not self._stop_requested:
            await self._wait_if_paused()
            if self._stop_requested:
                break

            if workflow.info().is_continue_as_new_suggested():
                workflow.logger.info("Histórico extenso — continuando como novo workflow.")
                workflow.continue_as_new(args=[max_kills, screenshot_every_kills, self._stats])

            enemy = await workflow.execute_activity(
                scan_for_enemy,
                schedule_to_close_timeout=timedelta(seconds=5),
                retry_policy=GAME_RETRY,
            )

            if not enemy["found"]:
                await workflow.sleep(timedelta(seconds=1))
                continue

            if enemy["hazard"]:
                workflow.logger.warning(
                    "Inimigo hazard '%s' em (%d,%d) — recuando sem engajar.",
                    enemy["type"], enemy["x"], enemy["y"]
                )
                await workflow.execute_activity(
                    retreat_from_hazard,
                    schedule_to_close_timeout=timedelta(seconds=10),
                    retry_policy=NO_RETRY,
                )
                await workflow.sleep(timedelta(seconds=10))
                continue

            workflow.logger.info(
                "Inimigo '%s' em (%d,%d)", enemy["type"], enemy["x"], enemy["y"]
            )

            result = await workflow.execute_activity(
                engage_enemy,
                args=[enemy["x"], enemy["y"]],
                schedule_to_close_timeout=timedelta(seconds=30),
                heartbeat_timeout=timedelta(seconds=5),
                retry_policy=NO_RETRY,
            )

            if result == "killed":
                self._stats["kills"] += 1
                kills = self._stats["kills"]
                workflow.logger.info("Kill #%d.", kills)
                if screenshot_every_kills > 0 and kills % screenshot_every_kills == 0:
                    await _screenshot(f"kill_{kills}")

            elif result == "died":
                self._stats["deaths"] += 1
                workflow.logger.warning("Morreu (morte #%d). Respawnando...", self._stats["deaths"])
                await workflow.execute_activity(
                    handle_death_respawn,
                    schedule_to_close_timeout=timedelta(seconds=15),
                    retry_policy=NAV_RETRY,
                )
                await workflow.sleep(timedelta(seconds=5))

            elif result == "escaped":
                self._stats["escaped"] += 1
                workflow.logger.info("Fugiu (vida baixa). Aguardando regeneração.")
                await workflow.sleep(timedelta(seconds=8))

        self._stats["status"] = "stopped"
        await _save_stats("CombatPatrolWorkflow", self._stats)
        return self._stats


# ---------------------------------------------------------------------------
# Workflow: Sessão AFK Completa
# ---------------------------------------------------------------------------

@workflow.defn
class AfkSessionWorkflow(_ControlMixin):
    """
    Rotações alternadas de gift farm + patrulha de combate.

    Parâmetros:
        gift_cycles (int):                  Ciclos de gift por rotação [10]
        combat_kills_per_rotation (int):    Kills de combate por rotação [5]
        total_rotations (int):              Total de rotações [20]
        screenshot_every_rotations (int):   Screenshot a cada N rotações [1]

    Query get_stats retorna:
        {rotation, total_gifts, total_kills, total_ammo, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {
            "rotation": 0,
            "total_gifts": 0,
            "total_kills": 0,
            "total_ammo": 0,
            "status": "running",
        }

    @workflow.run
    async def run(
        self,
        gift_cycles: int = 10,
        combat_kills_per_rotation: int = 5,
        total_rotations: int = 20,
        screenshot_every_rotations: int = 1,
    ) -> dict:
        try:
            return await self._run_session(
                gift_cycles, combat_kills_per_rotation, total_rotations, screenshot_every_rotations
            )
        except asyncio.CancelledError:
            workflow.logger.warning("AfkSessionWorkflow cancelado — limpando estado do jogo.")
            await asyncio.shield(_cleanup_on_cancel("AfkSessionWorkflow"))
            raise

    async def _run_session(
        self,
        gift_cycles: int,
        combat_kills_per_rotation: int,
        total_rotations: int,
        screenshot_every_rotations: int,
    ) -> dict:
        for rotation in range(total_rotations):
            if self._stop_requested:
                break
            await self._wait_if_paused()

            self._stats["rotation"] = rotation + 1
            workflow.logger.info(
                "=== Rotação %d/%d | gifts=%d kills=%d ===",
                rotation + 1, total_rotations,
                self._stats["total_gifts"], self._stats["total_kills"]
            )

            if screenshot_every_rotations > 0 and (rotation + 1) % screenshot_every_rotations == 0:
                await _screenshot(f"rotation_{rotation + 1}")

            # Fase 1: Gift farm
            for _ in range(gift_cycles):
                if self._stop_requested:
                    break
                await self._wait_if_paused()

                collected = await workflow.execute_activity(
                    collect_doggo_gift,
                    schedule_to_close_timeout=timedelta(seconds=15),
                    retry_policy=GAME_RETRY,
                )
                if collected:
                    self._stats["total_gifts"] += 1

                inv_full = await workflow.execute_activity(
                    check_inventory_full,
                    schedule_to_close_timeout=timedelta(seconds=5),
                    retry_policy=GAME_RETRY,
                )
                if inv_full:
                    await _run_craft_cycle(ammo_per_craft=50)
                    self._stats["total_ammo"] += 50

                await workflow.sleep(timedelta(seconds=3))

            # Fase 2: Combate
            kills_this_rotation = 0
            while kills_this_rotation < combat_kills_per_rotation and not self._stop_requested:
                await self._wait_if_paused()

                enemy = await workflow.execute_activity(
                    scan_for_enemy,
                    schedule_to_close_timeout=timedelta(seconds=5),
                    retry_policy=GAME_RETRY,
                )
                if not enemy["found"]:
                    await workflow.sleep(timedelta(seconds=1))
                    continue

                if enemy["hazard"]:
                    workflow.logger.warning(
                        "Inimigo hazard '%s' em (%d,%d) — recuando sem engajar.",
                        enemy["type"], enemy["x"], enemy["y"]
                    )
                    await workflow.execute_activity(
                        retreat_from_hazard,
                        schedule_to_close_timeout=timedelta(seconds=10),
                        retry_policy=NO_RETRY,
                    )
                    await workflow.sleep(timedelta(seconds=10))
                    continue

                result = await workflow.execute_activity(
                    engage_enemy,
                    args=[enemy["x"], enemy["y"]],
                    schedule_to_close_timeout=timedelta(seconds=30),
                    heartbeat_timeout=timedelta(seconds=5),
                    retry_policy=NO_RETRY,
                )
                if result == "killed":
                    self._stats["total_kills"] += 1
                    kills_this_rotation += 1
                elif result == "died":
                    await workflow.execute_activity(
                        handle_death_respawn,
                        schedule_to_close_timeout=timedelta(seconds=15),
                        retry_policy=NAV_RETRY,
                    )
                    await workflow.sleep(timedelta(seconds=5))

                await workflow.sleep(timedelta(seconds=2))

        self._stats["status"] = "completed"
        await _save_stats("AfkSessionWorkflow", self._stats)
        return self._stats


# ---------------------------------------------------------------------------
# Workflow: Colheita Manual de Recursos
# ---------------------------------------------------------------------------

@workflow.defn
class ResourceHarvestWorkflow(_ControlMixin):
    """
    Loop de colheita manual em um node de recurso fixo. O jogador precisa
    estar posicionado dentro do alcance de interação do node antes de
    disparar o workflow — não há navegação/pathfinding até o node.

    Parâmetros:
        swings_per_cycle (int):        Interações por ciclo [20]
        cycles (int):                  0 = infinito até 'stop', N = encerra após N ciclos [0]
        screenshot_every_cycles (int): Screenshot a cada N ciclos [10]

    Query get_stats retorna:
        {cycles, total_swings, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {"cycles": 0, "total_swings": 0, "status": "running"}

    @workflow.run
    async def run(
        self,
        swings_per_cycle: int = 20,
        cycles: int = 0,
        screenshot_every_cycles: int = 10,
        _resume_stats: Optional[dict] = None,
    ) -> dict:
        if _resume_stats is not None:
            self._stats = _resume_stats
        workflow.logger.info("ResourceHarvestWorkflow iniciado. swings_per_cycle=%d", swings_per_cycle)

        # Orçamento de timeout dimensionado a partir do próprio swings_per_cycle,
        # para acompanhar o tempo real da activity em vez de um valor fixo.
        per_attempt = timedelta(seconds=swings_per_cycle * 1.5 + 10)
        schedule_to_close = per_attempt * GAME_RETRY.maximum_attempts + timedelta(seconds=10)

        try:
            while not self._stop_requested:
                await self._wait_if_paused()
                if self._stop_requested:
                    break
                if cycles > 0 and self._stats["cycles"] >= cycles:
                    break

                if workflow.info().is_continue_as_new_suggested():
                    workflow.logger.info("Histórico extenso — continuando como novo workflow.")
                    workflow.continue_as_new(
                        args=[swings_per_cycle, cycles, screenshot_every_cycles, self._stats]
                    )

                self._stats["cycles"] += 1
                cycle = self._stats["cycles"]

                if screenshot_every_cycles > 0 and cycle % screenshot_every_cycles == 0:
                    await _screenshot(f"harvest_cycle_{cycle}")

                swings = await workflow.execute_activity(
                    harvest_resource_node,
                    args=[swings_per_cycle],
                    start_to_close_timeout=per_attempt,
                    schedule_to_close_timeout=schedule_to_close,
                    heartbeat_timeout=timedelta(seconds=8),
                    retry_policy=GAME_RETRY,
                )
                self._stats["total_swings"] += swings

                await workflow.sleep(timedelta(seconds=2))

            self._stats["status"] = "stopped"
            await _save_stats("ResourceHarvestWorkflow", self._stats)
            return self._stats
        except asyncio.CancelledError:
            workflow.logger.warning("ResourceHarvestWorkflow cancelado — limpando estado do jogo.")
            await asyncio.shield(_cleanup_on_cancel("ResourceHarvestWorkflow"))
            raise


# ---------------------------------------------------------------------------
# Workflow: Domesticação de Lizard Doggo
# ---------------------------------------------------------------------------

@workflow.defn
class TameDoggoWorkflow(_ControlMixin):
    """
    Tenta domesticar um Lizard Doggo selvagem oferecendo Paleberry repetidas
    vezes (múltiplos doggos competem pela mesma berry, então repetir ajuda).

    O sucesso real — Doggo comeu, pulou e "chiou" — não é verificado
    automaticamente (cue visual fraco demais para template matching
    confiável). Best-effort: revise os screenshots de cada tentativa
    manualmente em debug_screenshots/.

    Parâmetros:
        max_attempts (int):              Tentativas de alimentação [5]
        seconds_between_attempts (int):  Espera entre tentativas [15]

    Query get_stats retorna:
        {attempts, fed, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {"attempts": 0, "fed": 0, "status": "running"}

    @workflow.run
    async def run(self, max_attempts: int = 5, seconds_between_attempts: int = 15) -> dict:
        workflow.logger.info("TameDoggoWorkflow iniciado. max_attempts=%d", max_attempts)
        try:
            while self._stats["attempts"] < max_attempts and not self._stop_requested:
                await self._wait_if_paused()
                if self._stop_requested:
                    break

                self._stats["attempts"] += 1
                attempt = self._stats["attempts"]

                fed = await workflow.execute_activity(
                    feed_wild_doggo,
                    start_to_close_timeout=timedelta(seconds=10),
                    schedule_to_close_timeout=timedelta(seconds=30),
                    retry_policy=GAME_RETRY,
                )
                if fed:
                    self._stats["fed"] += 1
                    await _screenshot(f"tame_attempt_{attempt}")

                await workflow.sleep(timedelta(seconds=seconds_between_attempts))

            self._stats["status"] = "stopped"
            await _save_stats("TameDoggoWorkflow", self._stats)
            return self._stats
        except asyncio.CancelledError:
            workflow.logger.warning("TameDoggoWorkflow cancelado — limpando estado do jogo.")
            await asyncio.shield(_cleanup_on_cancel("TameDoggoWorkflow"))
            raise


@workflow.defn
class TemplateOrchestrationWorkflow:
    """
    Workflow para automatizar a captura de templates e verificação visual.
    
    Parâmetros:
        target (str): "hud" ou "workshop"
        resolution (str): "2560x1440"
    """

    @workflow.run
    async def run(self, target: str = "hud", resolution: str = "2560x1440") -> dict:
        workflow.logger.info("TemplateOrchestrationWorkflow iniciado para alvo: %s", target)
        
        if target == "hud":
            screenshot = await workflow.execute_activity(
                capture_template_screen,
                args=["hud_base", "", ""],
                schedule_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
        elif target == "workshop":
            screenshot = await workflow.execute_activity(
                capture_template_screen,
                args=["workshop_base", "e", "escape"],
                schedule_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
        else:
            raise ValueError(f"Alvo desconhecido: {target}")
            
        extracted = await workflow.execute_activity(
            extract_templates_from_screen,
            args=[screenshot, target, resolution],
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        
        template_names = list(extracted.keys())
        verification = await workflow.execute_activity(
            verify_matching_templates,
            args=[template_names],
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        
        return {
            "screenshot": screenshot,
            "extracted_templates": extracted,
            "verification_results": verification,
        }


# ---------------------------------------------------------------------------
# Workflow: Expedição de Combate (ir, matar, reabastecer, voltar, guardar)
# ---------------------------------------------------------------------------

@workflow.defn
class CombatExpeditionWorkflow(_ControlMixin):
    """
    Expedição completa de combate:
    1. Verifica munição na base — crafta antes de partir se estiver baixa.
    2. Navega até 'location' (config.toml [locations.<location>]).
    3. Mata inimigos até max_kills, reaproveitando o mesmo loop de
       engage_enemy do CombatPatrolWorkflow (saúde/fuga e loot de remains já
       tratados ali; inimigos hazard são evitados, não engajados).
    4. Se a munição cair abaixo do mínimo no meio da expedição, volta para
       a base, crafta mais, e retorna ao mesmo local automaticamente.
    5. Ao atingir max_kills (ou receber 'stop'), volta para a base e abre um
       storage container para depositar o loot (shift-click no grid do
       inventário — best-effort, ver open_storage_and_deposit_loot).

    Parâmetros:
        location (str):               Nome do local de combate em [locations.<location>] — obrigatório
        max_kills (int):               Kills para encerrar a expedição [10]
        min_ammo_to_depart (int):      Munição mínima para sair/continuar sem reabastecer [20]
        ammo_per_craft (int):          Munição craftada por ciclo de reabastecimento [50]
        screenshot_every_kills (int):  Screenshot a cada N kills [5]
        base_location (str):           Nome do local de retorno em [locations.<name>] ["base"]
        nav_timeout_seconds (int):     Orçamento de tempo por tentativa de navegação [45]

    Query get_stats retorna:
        {kills, deaths, escaped, resupply_trips, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {
            "kills": 0, "deaths": 0, "escaped": 0,
            "resupply_trips": 0, "status": "running",
        }

    @workflow.run
    async def run(
        self,
        location: str,
        max_kills: int = 10,
        min_ammo_to_depart: int = 20,
        ammo_per_craft: int = 50,
        screenshot_every_kills: int = 5,
        base_location: str = "base",
        nav_timeout_seconds: int = 45,
    ) -> dict:
        workflow.logger.info(
            "CombatExpeditionWorkflow iniciado. location=%s max_kills=%d", location, max_kills
        )
        nav_start_to_close = timedelta(seconds=nav_timeout_seconds)
        nav_schedule_to_close = nav_start_to_close * NAV_RETRY.maximum_attempts + timedelta(seconds=20)

        async def _go(target: str) -> None:
            await workflow.execute_activity(
                navigate_to_location,
                args=[target],
                start_to_close_timeout=nav_start_to_close,
                schedule_to_close_timeout=nav_schedule_to_close,
                heartbeat_timeout=timedelta(seconds=8),
                retry_policy=NAV_RETRY,
            )

        async def _ammo() -> int:
            return await workflow.execute_activity(
                check_ammo_count,
                schedule_to_close_timeout=timedelta(seconds=10),
                retry_policy=NO_RETRY,
            )

        try:
            ammo = await _ammo()
            if 0 <= ammo < min_ammo_to_depart:
                workflow.logger.info("Munição inicial baixa (%d) — craftando antes de partir.", ammo)
                await _run_craft_cycle(ammo_per_craft)
                self._stats["resupply_trips"] += 1

            await _go(location)

            while self._stats["kills"] < max_kills and not self._stop_requested:
                await self._wait_if_paused()
                if self._stop_requested:
                    break

                ammo = await _ammo()
                if 0 <= ammo < min_ammo_to_depart:
                    workflow.logger.warning("Munição baixa (%d) — voltando para reabastecer.", ammo)
                    self._stats["resupply_trips"] += 1
                    await _go(base_location)
                    await _run_craft_cycle(ammo_per_craft)
                    await _go(location)
                    continue

                enemy = await workflow.execute_activity(
                    scan_for_enemy,
                    schedule_to_close_timeout=timedelta(seconds=5),
                    retry_policy=GAME_RETRY,
                )
                if not enemy["found"]:
                    await workflow.sleep(timedelta(seconds=1))
                    continue

                if enemy["hazard"]:
                    workflow.logger.warning(
                        "Inimigo hazard '%s' em (%d,%d) — recuando sem engajar.",
                        enemy["type"], enemy["x"], enemy["y"]
                    )
                    await workflow.execute_activity(
                        retreat_from_hazard,
                        schedule_to_close_timeout=timedelta(seconds=10),
                        retry_policy=NO_RETRY,
                    )
                    await workflow.sleep(timedelta(seconds=10))
                    continue

                result = await workflow.execute_activity(
                    engage_enemy,
                    args=[enemy["x"], enemy["y"]],
                    schedule_to_close_timeout=timedelta(seconds=30),
                    heartbeat_timeout=timedelta(seconds=5),
                    retry_policy=NO_RETRY,
                )

                if result == "killed":
                    self._stats["kills"] += 1
                    kills = self._stats["kills"]
                    workflow.logger.info("Kill #%d/%d.", kills, max_kills)
                    if screenshot_every_kills > 0 and kills % screenshot_every_kills == 0:
                        await _screenshot(f"expedition_kill_{kills}")
                elif result == "died":
                    self._stats["deaths"] += 1
                    workflow.logger.warning("Morreu (morte #%d). Respawnando...", self._stats["deaths"])
                    await workflow.execute_activity(
                        handle_death_respawn,
                        schedule_to_close_timeout=timedelta(seconds=15),
                        retry_policy=NAV_RETRY,
                    )
                    await workflow.sleep(timedelta(seconds=5))
                elif result == "escaped":
                    self._stats["escaped"] += 1
                    workflow.logger.info("Fugiu (vida baixa). Aguardando regeneração.")
                    await workflow.sleep(timedelta(seconds=8))

            workflow.logger.info("Expedição concluída — voltando para a base.")
            await _go(base_location)
            await workflow.execute_activity(
                open_storage_and_deposit_loot,
                start_to_close_timeout=timedelta(seconds=20),
                schedule_to_close_timeout=timedelta(seconds=70),
                retry_policy=GAME_RETRY,
            )

            self._stats["status"] = "completed"
            await _save_stats("CombatExpeditionWorkflow", self._stats)
            return self._stats
        except asyncio.CancelledError:
            workflow.logger.warning("CombatExpeditionWorkflow cancelado — limpando estado do jogo.")
            await asyncio.shield(_cleanup_on_cancel("CombatExpeditionWorkflow"))
            raise
