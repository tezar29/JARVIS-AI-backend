"""Tests d'intégration de l'orchestrateur (app/ai/orchestrator.py, étape 5) —
le cycle complet : routage d'intention, appel LLM (simulé), exécution
d'outil, persistance en base."""
import pytest
from sqlalchemy import select

from app.ai import orchestrator
from app.ai.llm.schemas import LLMResponse, ToolCall
from app.models.conversation import Message
from app.models.reminder import Reminder
from app.models.user import User



async def _make_user(db_session) -> User:
    user = User(email="clarence@jarvis.ai", password_hash="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_simple_conversation_turn_persists_messages(db_session, monkeypatch):
    user = await _make_user(db_session)
    conversation = await orchestrator.get_or_create_conversation(db_session, user, None, mode="text")

    async def fake_generate(messages, system, tools=None, require_tools=False):
        return LLMResponse(text="Bonjour Clarence, comment puis-je vous aider ?", tool_calls=[], provider="fake")

    monkeypatch.setattr(orchestrator.llm_router, "generate", fake_generate)

    result = await orchestrator.process_turn(db_session, user, conversation, "Bonjour Jarvis")

    assert result.text == "Bonjour Clarence, comment puis-je vous aider ?"
    assert result.agent_used == "conversational_agent"

    messages = (
        await db_session.execute(select(Message).where(Message.conversation_id == conversation.id))
    ).scalars().all()
    assert [m.role for m in messages] == ["user", "assistant"]


async def test_turn_with_tool_call_executes_and_writes_to_db(db_session, monkeypatch):
    user = await _make_user(db_session)
    conversation = await orchestrator.get_or_create_conversation(db_session, user, None, mode="text")

    calls = {"n": 0}

    async def fake_generate(messages, system, tools=None, require_tools=False):
        calls["n"] += 1
        if calls["n"] == 1:
            return LLMResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="create_reminder",
                        arguments={"title": "Payer la facture", "due_at": "2026-08-22T10:00:00"},
                    )
                ],
                provider="fake",
            )
        return LLMResponse(text="Rappel créé avec succès.", tool_calls=[], provider="fake")

    monkeypatch.setattr(orchestrator.llm_router, "generate", fake_generate)

    result = await orchestrator.process_turn(
        db_session, user, conversation, "Rappelle-moi de payer la facture demain à 10h"
    )

    assert result.text == "Rappel créé avec succès."
    assert result.agent_used == "automation_agent"

    reminders = (await db_session.execute(select(Reminder))).scalars().all()
    assert len(reminders) == 1
    assert reminders[0].title == "Payer la facture"


async def test_turn_without_any_llm_configured_returns_friendly_fallback(db_session):
    """Sans mock : aucun fournisseur LLM n'est configuré dans l'environnement
    de test (pas de clé API) — l'orchestrateur doit renvoyer un message
    clair plutôt que de lever une exception qui casserait la conversation."""
    user = await _make_user(db_session)
    conversation = await orchestrator.get_or_create_conversation(db_session, user, None, mode="text")

    result = await orchestrator.process_turn(db_session, user, conversation, "Bonjour")

    lowered = result.text.lower()
    assert "raisonnement" in lowered or "indisponible" in lowered or "configuré" in lowered


async def test_conversation_history_is_reused_across_turns(db_session, monkeypatch):
    user = await _make_user(db_session)
    conversation = await orchestrator.get_or_create_conversation(db_session, user, None, mode="text")

    seen_message_counts = []

    async def fake_generate(messages, system, tools=None, require_tools=False):
        seen_message_counts.append(len(messages))
        return LLMResponse(text="ok", tool_calls=[], provider="fake")

    monkeypatch.setattr(orchestrator.llm_router, "generate", fake_generate)

    await orchestrator.process_turn(db_session, user, conversation, "premier message")
    await orchestrator.process_turn(db_session, user, conversation, "second message")

    # Le second tour doit voir l'historique du premier (user+assistant) en plus du sien.
    assert seen_message_counts[1] > seen_message_counts[0]
