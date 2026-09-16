"""Provider GPT (OpenAI) — deuxième maillon de la chaîne de secours,
utilisé si Claude est indisponible ou volontairement préféré pour une
tâche donnée. Implémente le function calling au format OpenAI
(`tool_calls` / role="tool") traduit vers nos structures normalisées.
"""
import json

import httpx

from app.ai.llm.base import LLMProvider, LLMProviderUnavailable
from app.ai.llm.schemas import ChatMessage, LLMResponse, ToolCall, ToolDefinition
from app.core.config import settings

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(LLMProvider):
    name = "openai"
    supports_tools = True

    def is_configured(self) -> bool:
        return bool(settings.openai_api_key)

    def _build_messages(self, messages: list[ChatMessage], system: str) -> list[dict]:
        payload: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            if m.role == "tool":
                payload.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
            else:
                payload.append({"role": m.role, "content": m.content})
        return payload

    def _build_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
            }
            for t in tools
        ]

    async def generate(
        self,
        messages: list[ChatMessage],
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        if not self.is_configured():
            raise LLMProviderUnavailable("Clé API OpenAI manquante.")

        headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}
        payload: dict = {"model": DEFAULT_MODEL, "messages": self._build_messages(messages, system)}
        if tools:
            payload["tools"] = self._build_tools(tools)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(OPENAI_URL, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise LLMProviderUnavailable(f"OpenAI injoignable: {exc}") from exc

        if response.status_code != 200:
            raise LLMProviderUnavailable(f"OpenAI a répondu {response.status_code}: {response.text}")

        message = response.json()["choices"][0]["message"]
        tool_calls = [
            ToolCall(id=tc["id"], name=tc["function"]["name"], arguments=json.loads(tc["function"]["arguments"]))
            for tc in message.get("tool_calls") or []
        ]

        return LLMResponse(text=message.get("content") or "", tool_calls=tool_calls, provider=self.name)
