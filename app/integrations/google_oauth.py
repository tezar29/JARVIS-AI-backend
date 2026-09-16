"""Gestion du flux OAuth 2.0 Google (Calendar + Gmail partagent le même
token, avec des scopes combinés à l'autorisation).

Flux :
1. Le mobile ouvre `authorization_url()` dans un navigateur intégré (Custom Tabs / SFSafariViewController).
2. L'utilisateur autorise l'accès sur la page Google.
3. Google redirige vers `GOOGLE_OAUTH_REDIRECT_URI` avec un `code`.
4. Le backend échange ce code contre un access_token + refresh_token (`exchange_code`),
   les chiffre (AES-256) et les stocke dans `integrations`.
5. Avant chaque appel API, `get_valid_access_token` renvoie le token en le
   rafraîchissant automatiquement s'il a expiré.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.models.integration import Integration
from app.models.user import User

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

# Scopes minimaux nécessaires pour l'agenda et l'envoi d'emails —
# volontairement restreints (pas d'accès en lecture à la boîte mail
# entière, par exemple) pour limiter la surface de ce que JARVIS peut faire.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]


class GoogleIntegrationError(Exception):
    """Erreur générique d'intégration Google — non configurée, token
    invalide, ou appel API échoué."""


def _as_aware_utc(value: datetime) -> datetime:
    """Normalise un datetime en UTC timezone-aware. Certains drivers
    (SQLite en test, selon config) renvoient un datetime naïf même pour
    une colonne `DateTime(timezone=True)` — on le traite alors comme
    déjà en UTC plutôt que de planter la comparaison."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def is_configured() -> bool:
    return bool(settings.google_oauth_client_id and settings.google_oauth_client_secret)


def authorization_url(state: str) -> str:
    if not is_configured():
        raise GoogleIntegrationError("L'intégration Google n'est pas configurée côté serveur.")

    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",  # nécessaire pour obtenir un refresh_token
        "prompt": "consent",  # force le renvoi d'un refresh_token même si déjà autorisé avant
        "state": state,
    }
    return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"


async def exchange_code(db: AsyncSession, user: User, code: str) -> Integration:
    payload = {
        "code": code,
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(TOKEN_ENDPOINT, data=payload)

    if response.status_code != 200:
        raise GoogleIntegrationError(f"Échec de l'échange du code d'autorisation: {response.text}")

    data = response.json()
    return await _save_tokens(db, user, data)


async def _save_tokens(db: AsyncSession, user: User, token_data: dict) -> Integration:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))

    existing = await db.scalar(
        select(Integration).where(Integration.user_id == user.id, Integration.provider == "google")
    )

    encrypted_access = encrypt(token_data["access_token"])
    # Google ne renvoie un refresh_token qu'à la première autorisation
    # (ou si prompt=consent) : on garde l'ancien si absent de la réponse.
    new_refresh_token = token_data.get("refresh_token")

    if existing:
        existing.encrypted_access_token = encrypted_access
        if new_refresh_token:
            existing.encrypted_refresh_token = encrypt(new_refresh_token)
        existing.expires_at = expires_at
        existing.scopes = token_data.get("scope", " ".join(SCOPES))
        integration = existing
    else:
        if not new_refresh_token:
            raise GoogleIntegrationError(
                "Aucun refresh_token reçu de Google — réessaie la connexion (l'utilisateur "
                "doit explicitement autoriser l'accès, `prompt=consent` devrait l'éviter)."
            )
        integration = Integration(
            user_id=user.id,
            provider="google",
            encrypted_access_token=encrypted_access,
            encrypted_refresh_token=encrypt(new_refresh_token),
            expires_at=expires_at,
            scopes=token_data.get("scope", " ".join(SCOPES)),
        )
        db.add(integration)

    await db.commit()
    await db.refresh(integration)
    return integration


async def get_valid_access_token(db: AsyncSession, user: User) -> str:
    """Renvoie un access_token valide, en le rafraîchissant automatiquement
    si nécessaire. Lève GoogleIntegrationError si l'utilisateur n'a pas
    connecté son compte Google."""
    integration = await db.scalar(
        select(Integration).where(Integration.user_id == user.id, Integration.provider == "google")
    )
    if not integration:
        raise GoogleIntegrationError(
            "Aucun compte Google connecté. L'utilisateur doit d'abord se connecter via "
            "GET /api/v1/integrations/google/connect."
        )

    if _as_aware_utc(integration.expires_at) > datetime.now(timezone.utc) + timedelta(seconds=60):
        return decrypt(integration.encrypted_access_token)

    if not integration.encrypted_refresh_token:
        raise GoogleIntegrationError("Token Google expiré et aucun refresh_token disponible — reconnexion nécessaire.")

    refresh_token = decrypt(integration.encrypted_refresh_token)
    payload = {
        "refresh_token": refresh_token,
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(TOKEN_ENDPOINT, data=payload)

    if response.status_code != 200:
        raise GoogleIntegrationError(f"Échec du rafraîchissement du token Google: {response.text}")

    data = response.json()
    data.setdefault("refresh_token", refresh_token)  # le refresh token ne change pas à ce type d'appel
    await _save_tokens(db, user, data)
    return data["access_token"]
