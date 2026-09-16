"""Provider Gemini (Google) — troisième maillon de la chaîne de secours.

⚠️ Limitation actuelle : conversation texte uniquement, sans function
calling. Si un agent avec des outils (ex. AutomationAgent) retombe sur
Gemini, il continuera la conversation normalement mais ne pourra pas
exécuter d'action — à combler si Gemini devient un provider prioritaire
pour un agent donné.
"""
import httpx

from app.ai.llm.base import LLMProvider, LLMProviderUnavailable
from app.ai.llm.schemas import ChatMessage, LLMResponse, ToolDefinition
from app.core.config import settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiProvider(LLMProvider):
    name = "gemini"
    supports_tools = False

    def is_configured(self) -> bool:
        return bool(settings.google_api_key)

    async def generate(
        self,
        messages: list[ChatMessage],
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        if not self.is_configured():
            raise LLMProviderUnavailable("Clé API Google manquante.")

        contents = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
            for m in messages
            if m.role in ("user", "assistant")
        ]

        url = GEMINI_URL.format(model=DEFAULT_MODEL, key=settings.google_api_key)
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise LLMProviderUnavailable(f"Gemini injoignable: {exc}") from exc

        if response.status_code != 200:
            raise LLMProviderUnavailable(f"Gemini a répondu {response.status_code}: {response.text}")

        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return LLMResponse(text=text, tool_calls=[], provider=self.name)
