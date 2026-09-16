"""Classe de base commune à tous les agents spécialisés.

Chaque agent définit son propre prompt système (sa "personnalité" et
son périmètre) et, le cas échéant, les outils qu'il peut appeler via
function calling. `execute_tool` est le point d'exécution réel d'une
action (écriture en base, appel à une intégration externe...) —
séparé du LLM lui-même pour rester testable indépendamment.

`remember_fact` est géré ici, au niveau de la base, car c'est le seul
outil commun à tous les agents (mémoire long terme, étape 6) : chaque
agent spécialisé qui l'ajoute à sa liste `tools` en bénéficie
automatiquement sans rien réimplémenter, tant que son `execute_tool`
retombe sur `super().execute_tool(...)` pour les outils qu'il ne
reconnaît pas lui-même (voir AutomationAgent pour l'exemple).
"""
from abc import ABC
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.schemas import ToolDefinition
from app.models.user import User


class BaseAgent(ABC):
    name: str = "base_agent"
    system_prompt: str = "Tu es JARVIS, un assistant personnel intelligent."
    tools: list[ToolDefinition] = []

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any], db: AsyncSession, user: User) -> str:
        """Exécute un outil demandé par le LLM et renvoie un résultat
        textuel qui sera réinjecté dans la conversation. À surcharger
        par les agents qui déclarent des `tools` spécifiques — l'agent
        doit retomber sur `super().execute_tool(...)` pour les outils
        qu'il ne reconnaît pas, afin d'hériter de `remember_fact`."""
        if tool_name == "remember_fact":
            from app.ai.memory.memory_service import remember  # import tardif : évite un cycle memory <-> agents

            content = (arguments.get("content") or "").strip()
            if not content:
                return "Échec : aucun contenu à mémoriser n'a été fourni."

            category = arguments.get("category", "fact")
            item = await remember(db, user, content, category)
            if item is None:
                return "Je retiens l'information pour cette conversation, mais la mémoire long terme n'est pas disponible actuellement (service d'embeddings non configuré)."
            return f"J'ai mémorisé : « {content} »."

        raise NotImplementedError(f"L'agent {self.name} n'implémente pas l'outil '{tool_name}'.")
