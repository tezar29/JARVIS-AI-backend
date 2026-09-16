"""Structures de données communes à tous les fournisseurs LLM.

Chaque provider (Anthropic, OpenAI, Gemini, Ollama) traduit son format
natif vers ces classes normalisées — c'est ce qui permet à
l'orchestrateur et aux agents de rester agnostiques du fournisseur
utilisé (routage multi-LLM transparent).
"""
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ChatMessage:
    role: Role
    content: str
    tool_call_id: str | None = None  # pour role="tool" : quel appel cette réponse concerne
    name: str | None = None  # pour role="tool" : nom de l'outil appelé


@dataclass
class ToolDefinition:
    """Définition d'un outil au format JSON Schema, indépendante du
    fournisseur — traduite au format natif dans chaque provider."""
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0
