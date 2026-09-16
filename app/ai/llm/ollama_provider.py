"""Provider Ollama — exécution locale d'un LLM open-source, dernier
maillon de la chaîne de secours.

Utile pour : (a) le mode 100% local/hors-cloud voulu par l'architecture,
(b) un dernier repli si aucun fournisseur cloud n'est configuré ou
joignable. Comme Gemini, pas de function calling pour l'instant —
certains modèles Ollama le supportent (ex. llama3.1) mais le format
diffère d'un modèle à l'autre, donc non généralisé ici.
"""
import httpx

from app.ai.llm.base import LLMProvider, LLMProviderUnavailable
from app.ai.llm.schemas import ChatMessage, LLMResponse, ToolDefinition
from app.core.config import settings

DEFAULT_MODEL = "llama3.1"


class OllamaProvider(LLMProvider):
    name = "ollama"
    supports_tools = False

    def is_configured(self) -> bool:
        # Toujours "configuré" dès lors qu'une URL est renseignée — la
        # vraie vérification de disponibilité se fait à l'appel (le
        # serveur Ollama local peut être éteint).
        return bool(settings.ollama_base_url)

    async def generate(
        self,
        messages: list[ChatMessage],
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        if not self.is_configured():
            raise LLMProviderUnavailable("URL Ollama non configurée.")

        payload = {
            "model": DEFAULT_MODEL,
            "stream": False,
            "messages": [{"role": "system", "content": system}]
            + [{"role": m.role, "content": m.content} for m in messages if m.role in ("user", "assistant")],
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise LLMProviderUnavailable(f"Ollama injoignable (serveur local éteint ?): {exc}") from exc

        if response.status_code != 200:
            raise LLMProviderUnavailable(f"Ollama a répondu {response.status_code}: {response.text}")

        text = response.json()["message"]["content"]
        return LLMResponse(text=text, tool_calls=[], provider=self.name)
