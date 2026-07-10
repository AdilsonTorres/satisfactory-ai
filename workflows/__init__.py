"""
Workflows package — re-exports all Temporal workflow classes.
"""

from workflows.afk_session import AfkSessionWorkflow
from workflows.combat_expedition import CombatExpeditionWorkflow
from workflows.combat_patrol import CombatPatrolWorkflow
from workflows.control import SignalWorkflowAction
from workflows.depot_coal import DepotCoalToStorageWorkflow
from workflows.exploration import ExplorationWorkflow
from workflows.gift_farm import GiftFarmWorkflow
from workflows.resource_harvest import ResourceHarvestWorkflow
from workflows.tame_doggo import TameDoggoWorkflow
from workflows.template_orchestration import TemplateOrchestrationWorkflow

ALL_WORKFLOWS = [
    AfkSessionWorkflow,
    CombatExpeditionWorkflow,
    CombatPatrolWorkflow,
    ExplorationWorkflow,
    GiftFarmWorkflow,
    ResourceHarvestWorkflow,
    SignalWorkflowAction,
    TameDoggoWorkflow,
    TemplateOrchestrationWorkflow,
    DepotCoalToStorageWorkflow,
]
