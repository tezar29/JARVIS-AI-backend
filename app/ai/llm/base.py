"""Interface abstraite qu'implémente chaque fournisseur LLM."""
from abc import ABC, abstractmethod

from app.ai.llm.schemas import ChatMessage, LLMResponse, ToolDefinition


class LLMProviderUnavailable(Exception):
    """Levée quand un provider n'est pas configuré (clé API absente) ou
    injoignable — permet au LLMRouter de basculer sur le suivant de la
    chaîne de secours sans faire planter la conversation."""


class LLMProvider(ABC):
    name: str = "base"
    supports_tools: bool = False

    @abstractmethod
    def is_configured(self) -> bool:
        """True si la clé API / l'URL nécessaire est renseignée."""

    @abstractmethod
    async def generate(
        self,
        messages: list[ChatMessage],
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Génère une réponse. Lève LLMProviderUnavailable si le
        provider n'est pas utilisable (non configuré ou erreur réseau)."""
