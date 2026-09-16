"""Routeur multi-LLM : essaie chaque fournisseur configuré dans l'ordre
de priorité jusqu'à ce que l'un d'eux réponde. Concrétise le "routage
multi-LLM" de l'architecture — résilience si un fournisseur est en
panne, mal configuré, ou en rate-limit.

Ordre par défaut : Claude → GPT → Gemini → Ollama (du plus capable au
plus disponible/local). Un agent qui a besoin d'outils (function
calling) doit le signaler via `require_tools=True` : le routeur ignore
alors les providers qui ne le supportent pas (Gemini, Ollama).
"""
import logging

from app.ai.llm.anthropic_provider import AnthropicProvider
from app.ai.llm.base import LLMProvider, LLMProviderUnavailable
from app.ai.llm.gemini_provider import GeminiProvider
from app.ai.llm.ollama_provider import OllamaProvider
from app.ai.llm.openai_provider import OpenAIProvider
from app.ai.llm.schemas import ChatMessage, LLMResponse, ToolDefinition

logger = logging.getLogger("jarvis.llm_router")


class LLMRouter:
    def __init__(self) -> None:
        self._providers: list[LLMProvider] = [
            AnthropicProvider(),
            OpenAIProvider(),
            GeminiProvider(),
            OllamaProvider(),
        ]

    async def generate(
        self,
        messages: list[ChatMessage],
        system: str,
        tools: list[ToolDefinition] | None = None,
        require_tools: bool = False,
    ) -> LLMResponse:
        candidates = [p for p in self._providers if p.is_configured()]
        if require_tools:
            candidates = [p for p in candidates if p.supports_tools]

        if not candidates:
            raise LLMProviderUnavailable(
                "Aucun fournisseur LLM disponible : configure au moins une clé API "
                "(ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY) ou un serveur Ollama local."
            )

        last_error: Exception | None = None
        for provider in candidates:
            try:
                return await provider.generate(messages, system, tools if provider.supports_tools else None)
            except LLMProviderUnavailable as exc:
                logger.warning("Provider %s indisponible, bascule sur le suivant: %s", provider.name, exc)
                last_error = exc
                continue

        raise LLMProviderUnavailable(f"Tous les fournisseurs LLM ont échoué. Dernière erreur: {last_error}")


llm_router = LLMRouter()
