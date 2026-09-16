"""Provider Claude (Anthropic) — fournisseur par défaut de JARVIS AI.

Implémente le function calling natif d'Anthropic (blocs de contenu
`tool_use` / `tool_result`) et le traduit vers/depuis nos structures
normalisées (ChatMessage, ToolCall, LLMResponse).
"""
import httpx

from app.ai.llm.base import LLMProvider, LLMProviderUnavailable
from app.ai.llm.schemas import ChatMessage, LLMResponse, ToolCall, ToolDefinition
from app.core.config import settings

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    supports_tools = True

    def is_configured(self) -> bool:
        return bool(settings.anthropic_api_key)

    def _build_messages(self, messages: list[ChatMessage]) -> list[dict]:
        """Regroupe les résultats d'outils (role="tool") dans un bloc
        `tool_result` côté utilisateur, comme l'exige l'API Anthropic."""
        payload: list[dict] = []
        for m in messages:
            if m.role == "tool":
                payload.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id,
                                "content": m.content,
                            }
                        ],
                    }
                )
            else:
                payload.append({"role": m.role, "content": m.content})
        return payload

    def _build_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]

    async def generate(
        self,
        messages: list[ChatMessage],
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        if not self.is_configured():
            raise LLMProviderUnavailable("Clé API Anthropic manquante.")

        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        payload: dict = {
            "model": DEFAULT_MODEL,
            "max_tokens": 1024,
            "system": system,
            "messages": self._build_messages(messages),
        }
        if tools:
            payload["tools"] = self._build_tools(tools)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(ANTHROPIC_URL, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise LLMProviderUnavailable(f"Anthropic injoignable: {exc}") from exc

        if response.status_code != 200:
            raise LLMProviderUnavailable(f"Anthropic a répondu {response.status_code}: {response.text}")

        data = response.json()
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in data.get("content", []):
            if block["type"] == "text":
                text_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCall(id=block["id"], name=block["name"], arguments=block["input"]))

        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls, provider=self.name)
