"""Client Gmail — envoi d'emails au nom de l'utilisateur (scope
`gmail.send` uniquement : JARVIS peut envoyer des emails mais ne peut
jamais lire la boîte de réception, par choix de conception minimisant
les autorisations accordées)."""
import base64
from email.message import EmailMessage

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.google_oauth import GoogleIntegrationError, get_valid_access_token
from app.models.user import User

GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


async def send_email(db: AsyncSession, user: User, to: str, subject: str, body: str) -> None:
    access_token = await get_valid_access_token(db, user)

    message = EmailMessage()
    message["To"] = to
    message["From"] = "me"
    message["Subject"] = subject
    message.set_content(body)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(GMAIL_SEND_URL, headers=headers, json={"raw": raw})

    if response.status_code not in (200, 202):
        raise GoogleIntegrationError(f"Échec de l'envoi de l'email: {response.text}")
