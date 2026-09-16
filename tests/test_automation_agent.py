"""Tests d'intégration de l'agent d'automatisation (app/ai/agents/automation_agent.py,
étapes 5 et 7) — écriture réelle en base, gestion des cas d'échec sans crash."""
import pytest
from sqlalchemy import select

from app.ai.agents.automation_agent import AutomationAgent
from app.models.reminder import Reminder
from app.models.user import User



async def _make_user(db_session) -> User:
    user = User(email="clarence@jarvis.ai", password_hash="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_create_reminder_writes_to_db(db_session):
    user = await _make_user(db_session)
    agent = AutomationAgent()

    result = await agent.execute_tool(
        "create_reminder",
        {"title": "Payer la facture", "due_at": "2026-08-22T10:00:00"},
        db_session,
        user,
    )

    assert "Payer la facture" in result
    reminders = (await db_session.execute(select(Reminder))).scalars().all()
    assert len(reminders) == 1
    assert reminders[0].title == "Payer la facture"


async def test_create_reminder_invalid_date_does_not_crash(db_session):
    user = await _make_user(db_session)
    agent = AutomationAgent()

    result = await agent.execute_tool(
        "create_reminder", {"title": "x", "due_at": "pas-une-date"}, db_session, user
    )

    assert "Échec" in result
    reminders = (await db_session.execute(select(Reminder))).scalars().all()
    assert len(reminders) == 0


async def test_create_event_without_google_connected_returns_clear_message(db_session):
    user = await _make_user(db_session)
    agent = AutomationAgent()

    result = await agent.execute_tool(
        "create_event",
        {"title": "Réunion", "start": "2026-08-22T10:00:00", "end": "2026-08-22T11:00:00"},
        db_session,
        user,
    )

    assert "connect" in result.lower() or "connecté" in result.lower()


async def test_send_whatsapp_without_server_config_returns_clear_message(db_session):
    user = await _make_user(db_session)
    agent = AutomationAgent()

    result = await agent.execute_tool(
        "send_whatsapp_message", {"to_phone": "+237600000000", "text": "Salut"}, db_session, user
    )

    assert "whatsapp" in result.lower()


async def test_unknown_tool_raises_not_implemented(db_session):
    user = await _make_user(db_session)
    agent = AutomationAgent()

    with pytest.raises(NotImplementedError):
        await agent.execute_tool("outil_inexistant", {}, db_session, user)
