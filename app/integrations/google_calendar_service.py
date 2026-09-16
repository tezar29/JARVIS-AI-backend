"""Client Google Calendar — utilisé par l'agent d'automatisation pour
créer de vrais événements dans l'agenda Google de l'utilisateur (par
opposition aux rappels internes, propres à JARVIS, de l'étape 5)."""
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.google_oauth import GoogleIntegrationError, get_valid_access_token
from app.models.user import User

CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


async def create_event(db: AsyncSession, user: User, title: str, start: datetime, end: datetime) -> str:
    """Crée un événement dans l'agenda Google principal de l'utilisateur.
    Renvoie le lien vers l'événement créé. Lève GoogleIntegrationError si
    le compte n'est pas connecté ou si l'appel échoue."""
    access_token = await get_valid_access_token(db, user)

    payload = {
        "summary": title,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(CALENDAR_EVENTS_URL, headers=headers, json=payload)

    if response.status_code not in (200, 201):
        raise GoogleIntegrationError(f"Échec de la création de l'événement: {response.text}")

    return response.json().get("htmlLink", "")
