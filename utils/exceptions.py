"""
utils/exceptions.py
Hierarquia de exceções do bot.
Nomes descritivos aparecem no histórico do Temporal para facilitar o debug.
"""


class SatisfactoryBotError(Exception):
    """Erro base — todos os erros do bot herdam daqui."""


class VisionError(SatisfactoryBotError):
    """Template não encontrado na tela com confiança suficiente."""

    def __init__(self, template: str, confidence: float, threshold: float):
        self.template = template
        self.confidence = confidence
        self.threshold = threshold
        super().__init__(
            f"Template '{template}' não encontrado. "
            f"Melhor conf: {confidence:.3f} < threshold: {threshold:.3f}. "
            f"Rode: uv run python debug_run.py --find {template}"
        )


class NavigationError(SatisfactoryBotError):
    """Workshop ou destino não encontrado após sequência de movimento."""


class MenuError(SatisfactoryBotError):
    """Menu não abriu ou não está no estado esperado."""


class CombatError(SatisfactoryBotError):
    """Estado inesperado durante combate."""


class RespawnError(SatisfactoryBotError):
    """Botão de respawn não encontrado na tela de morte."""
