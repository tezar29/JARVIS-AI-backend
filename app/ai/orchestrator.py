"""Orchestrateur central de JARVIS AI.

Point d'entrée unique utilisé à la fois par le module vocal
(`api/v1/voice.py`) et par le chat texte (`api/v1/chat.py`) : les deux
canaux partagent exactement la même intelligence, seule la couche de
transport (WebSocket vocal vs texte) diffère.

Déroulé d'un tour de conversation :
1. Charge les derniers messages de la conversation (mémoire court terme).
2. Recherche les souvenirs long terme pertinents pour la requête (RAG,
   étape 6) et les injecte dans le prompt système.
3. Route vers l'agent spécialisé pertinent (conversation / automatisation / productivité).
4. Appelle le LLM (via le routeur multi-fournisseur) avec le prompt système
   augmenté et les outils éventuels de l'agent (dont remember_fact, commun
   à tous — voir base_agent.py).
5. Si le LLM demande l'exécution d'un outil (function calling), l'agent
   l'exécute réellement (ex: création d'un rappel, mémorisation d'un fait),
   puis on redemande une réponse finale au LLM avec le résultat de l'outil.
6. Persiste les messages (utilisateur + assistant) et renvoie le texte final.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.automation_agent import AutomationAgent
from app.ai.agents.base_agent import BaseAgent
from app.ai.agents.conversational_agent import ConversationalAgent
from app.ai.agents.intent_router import classify_intent
from app.ai.agents.productivity_agent import ProductivityAgent
from app.ai.agents.types import AgentType
from app.ai.llm.base import LLMProviderUnavailable
from app.ai.llm.router import llm_router
from app.ai.llm.schemas import ChatMessage
from app.ai.memory.memory_service import search_relevant_memories
from app.models.conversation import Conversation, Message
from app.models.user import User

logger = logging.getLogger("jarvis.orchestrator")

_AGENTS: dict[AgentType, BaseAgent] = {
    AgentType.CONVERSATION: ConversationalAgent(),
    AgentType.AUTOMATION: AutomationAgent(),
    AgentType.PRODUCTIVITY: ProductivityAgent(),
}

_MAX_HISTORY_MESSAGES = 12  # mémoire court terme (session en cours) — voir search_relevant_memories pour le long terme (RAG)
_MAX_TOOL_ROUNDS = 2  # évite une boucle infinie d'appels d'outils


@dataclass
class TurnResult:
    text: str
    agent_used: str


async def get_or_create_conversation(db: AsyncSession, user: User, conversation_id, mode: str) -> Conversation:
    if conversation_id is not None:
        existing = await db.get(Conversation, conversation_id)
        if existing and existing.user_id == user.id:
            return existing

    conversation = Conversation(user_id=user.id, mode=mode)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def _load_history(db: AsyncSession, conversation: Conversation) -> list[ChatMessage]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(_MAX_HISTORY_MESSAGES)
    )
    rows = list(reversed(result.scalars().all()))
    return [ChatMessage(role=row.role, content=row.content) for row in rows if row.role in ("user", "assistant")]


async def _persist_message(
    db: AsyncSession, conversation: Conversation, role: str, content: str, agent_used: str | None = None
) -> None:
    db.add(Message(conversation_id=conversation.id, role=role, content=content, agent_used=agent_used))
    await db.commit()


def _augmented_system_prompt(agent: BaseAgent, relevant_memories: list[str]) -> str:
    """Ajoute la date/heure courante (pour résoudre les dates relatives,
    ex: "demain") et les souvenirs long terme pertinents (RAG) au prompt
    système de l'agent."""
    now = datetime.now(timezone.utc).strftime("%A %d %B %Y, %H:%M UTC")
    prompt = f"{agent.system_prompt}\n\nDate et heure actuelles : {now}."

    if relevant_memories:
        memories_block = "\n".join(f"- {m}" for m in relevant_memories)
        prompt += (
            "\n\nCe que tu sais déjà sur l'utilisateur (mémoire long terme, "
            f"utilise-le seulement si pertinent pour cette demande) :\n{memories_block}"
        )

    return prompt


async def process_turn(
    db: AsyncSession,
    user: User,
    conversation: Conversation,
    user_text: str,
) -> TurnResult:
    agent_type = classify_intent(user_text)
    agent = _AGENTS[agent_type]

    history = await _load_history(db, conversation)
    relevant_memories = await search_relevant_memories(db, user, user_text)
    await _persist_message(db, conversation, "user", user_text)

    messages = history + [ChatMessage(role="user", content=user_text)]
    system_prompt = _augmented_system_prompt(agent, relevant_memories)

    try:
        response = await llm_router.generate(
            messages, system=system_prompt, tools=agent.tools or None, require_tools=bool(agent.tools)
        )
    except LLMProviderUnavailable as exc:
        logger.error("Aucun LLM disponible: %s", exc)
        fallback_text = (
            "Je ne parviens pas à joindre mon moteur de raisonnement en ce moment "
            "(aucun fournisseur IA configuré ou tous indisponibles). "
            "Vérifie la configuration des clés API côté serveur."
        )
        await _persist_message(db, conversation, "assistant", fallback_text, agent.name)
        return TurnResult(text=fallback_text, agent_used=agent.name)

    rounds = 0
    while response.has_tool_calls and rounds < _MAX_TOOL_ROUNDS:
        rounds += 1
        tool_result_messages: list[ChatMessage] = []
        for call in response.tool_calls:
            result_text = await agent.execute_tool(call.name, call.arguments, db, user)
            tool_result_messages.append(
                ChatMessage(role="tool", content=result_text, tool_call_id=call.id, name=call.name)
            )

        messages = messages + [ChatMessage(role="assistant", content=response.text)] + tool_result_messages
        response = await llm_router.generate(messages, system=system_prompt, tools=agent.tools or None)

    final_text = response.text or "D'accord."
    await _persist_message(db, conversation, "assistant", final_text, agent.name)

    return TurnResult(text=final_text, agent_used=agent.name)


async def record_vision_exchange(
    db: AsyncSession, conversation: Conversation, user_caption: str, analysis_text: str
) -> None:
    """Persiste une analyse d'image (étape 8) dans l'historique de la
    conversation, au même titre qu'un tour de texte ou de voix — ainsi,
    un message vocal ou texte ultérieur dans la même conversation peut
    faire référence à "l'image que je viens d'envoyer" et l'agent aura
    le contexte nécessaire dans sa mémoire court terme."""
    await _persist_message(db, conversation, "user", user_caption)
    await _persist_message(db, conversation, "assistant", analysis_text, "vision_agent")
