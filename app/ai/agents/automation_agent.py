"""Agent d'automatisation — exécute de vraies actions via function
calling (plutôt que de simplement en parler) : rappels internes,
événements Google Agenda, emails Gmail, messages WhatsApp.

Chaque outil "externe" (create_event, send_email, send_whatsapp_message)
peut échouer si l'utilisateur n'a pas connecté le service correspondant
— dans ce cas, l'agent renvoie un message clair au LLM plutôt que de
lever une exception brute, pour que la réponse finale à l'utilisateur
reste utile ("connecte d'abord ton compte Google via les réglages").
"""
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.base_agent import BaseAgent
from app.ai.agents.shared_tools import REMEMBER_FACT_TOOL
from app.ai.llm.schemas import ToolDefinition
from app.integrations.gmail_service import send_email as gmail_send_email
from app.integrations.google_calendar_service import create_event as gcal_create_event
from app.integrations.google_oauth import GoogleIntegrationError
from app.integrations.whatsapp_service import WhatsAppIntegrationError, send_whatsapp_message
from app.models.reminder import Reminder
from app.models.user import User

SYSTEM_PROMPT = """Tu es le module d'automatisation de JARVIS. Ton rôle est \
d'exécuter des actions concrètes plutôt que de te contenter d'en discuter :
- create_reminder : un rappel interne à JARVIS (simple, toujours disponible).
- create_event : un vrai événement dans l'agenda Google de l'utilisateur \
(nécessite que l'utilisateur ait connecté son compte Google).
- send_email : un email envoyé depuis la boîte Gmail de l'utilisateur.
- send_whatsapp_message : un message WhatsApp (uniquement si le destinataire \
a déjà écrit au numéro JARVIS dans les 24 dernières heures — limite imposée \
par WhatsApp, pas par nous).

Pour toute date/heure, utilise le format ISO 8601 et déduis l'année/le mois/le \
jour à partir du contexte ("demain", "vendredi") en te basant sur la date du \
jour fournie dans le contexte de la conversation. Si un outil échoue parce que \
le service n'est pas connecté, explique clairement à l'utilisateur comment y \
remédier plutôt que d'inventer une confirmation. Confirme brièvement toute \
action réussie, dans la langue de l'utilisateur."""

CREATE_REMINDER_TOOL = ToolDefinition(
    name="create_reminder",
    description="Crée un rappel interne à JARVIS (ne nécessite aucune intégration externe).",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Le libellé court du rappel."},
            "due_at": {
                "type": "string",
                "description": "Date et heure d'échéance au format ISO 8601, ex: 2026-08-21T10:00:00",
            },
        },
        "required": ["title", "due_at"],
    },
)

CREATE_EVENT_TOOL = ToolDefinition(
    name="create_event",
    description="Crée un événement dans l'agenda Google de l'utilisateur (nécessite une connexion Google active).",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Titre de l'événement."},
            "start": {"type": "string", "description": "Début au format ISO 8601, ex: 2026-08-21T10:00:00"},
            "end": {"type": "string", "description": "Fin au format ISO 8601, ex: 2026-08-21T11:00:00"},
        },
        "required": ["title", "start", "end"],
    },
)

SEND_EMAIL_TOOL = ToolDefinition(
    name="send_email",
    description="Envoie un email depuis la boîte Gmail de l'utilisateur (nécessite une connexion Google active).",
    parameters={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Adresse email du destinataire."},
            "subject": {"type": "string", "description": "Objet de l'email."},
            "body": {"type": "string", "description": "Corps du message."},
        },
        "required": ["to", "subject", "body"],
    },
)

SEND_WHATSAPP_TOOL = ToolDefinition(
    name="send_whatsapp_message",
    description=(
        "Envoie un message WhatsApp à un numéro donné. Ne fonctionne que si ce numéro a "
        "écrit au numéro professionnel de JARVIS dans les dernières 24h (politique WhatsApp)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "to_phone": {"type": "string", "description": "Numéro au format international, ex: +237600000000."},
            "text": {"type": "string", "description": "Contenu du message."},
        },
        "required": ["to_phone", "text"],
    },
)


class AutomationAgent(BaseAgent):
    name = "automation_agent"
    system_prompt = SYSTEM_PROMPT
    tools = [CREATE_REMINDER_TOOL, CREATE_EVENT_TOOL, SEND_EMAIL_TOOL, SEND_WHATSAPP_TOOL, REMEMBER_FACT_TOOL]

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any], db: AsyncSession, user: User) -> str:
        if tool_name == "create_reminder":
            return await self._create_reminder(arguments, db, user)
        if tool_name == "create_event":
            return await self._create_event(arguments, db, user)
        if tool_name == "send_email":
            return await self._send_email(arguments, db, user)
        if tool_name == "send_whatsapp_message":
            return await self._send_whatsapp(arguments)

        return await super().execute_tool(tool_name, arguments, db, user)

    async def _create_reminder(self, arguments: dict[str, Any], db: AsyncSession, user: User) -> str:
        try:
            due_at = datetime.fromisoformat(arguments["due_at"])
        except (KeyError, ValueError):
            return "Échec : la date fournie n'est pas dans un format valide."

        reminder = Reminder(user_id=user.id, title=arguments["title"], due_at=due_at, status="pending")
        db.add(reminder)
        await db.commit()

        return f"Rappel « {reminder.title} » créé pour le {due_at.strftime('%d/%m/%Y à %H:%M')}."

    async def _create_event(self, arguments: dict[str, Any], db: AsyncSession, user: User) -> str:
        try:
            start = datetime.fromisoformat(arguments["start"])
            end = datetime.fromisoformat(arguments["end"])
        except (KeyError, ValueError):
            return "Échec : les dates de début/fin fournies ne sont pas dans un format valide."

        try:
            link = await gcal_create_event(db, user, arguments["title"], start, end)
        except GoogleIntegrationError as exc:
            return f"Échec : {exc} Pour connecter Google, va dans les réglages de l'application."

        return f"Événement « {arguments['title']} » créé dans ton agenda Google ({link})."

    async def _send_email(self, arguments: dict[str, Any], db: AsyncSession, user: User) -> str:
        try:
            await gmail_send_email(db, user, arguments["to"], arguments["subject"], arguments["body"])
        except GoogleIntegrationError as exc:
            return f"Échec : {exc} Pour connecter Gmail, va dans les réglages de l'application."

        return f"Email envoyé à {arguments['to']}."

    async def _send_whatsapp(self, arguments: dict[str, Any]) -> str:
        try:
            await send_whatsapp_message(arguments["to_phone"], arguments["text"])
        except WhatsAppIntegrationError as exc:
            return f"Échec de l'envoi WhatsApp : {exc}"

        return f"Message WhatsApp envoyé à {arguments['to_phone']}."
