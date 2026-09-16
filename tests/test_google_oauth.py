"""Tests du flux OAuth Google (app/integrations/google_oauth.py, étape 7).

Couvre en particulier le rafraîchissement automatique de token expiré —
un vrai bug (comparaison de dates naïve/timezone-aware) a été détecté
et corrigé grâce à ce test pendant le développement de l'étape 7 ; il
reste ici en garde-fou contre une régression.
"""
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import func, select

from app.core.crypto import decrypt
from app.integrations import google_oauth
from app.models.integration import Integration
from app.models.user import User



@pytest.fixture(autouse=True)
def _configure_google_oauth(monkeypatch):
    import app.core.config as cfg

    monkeypatch.setattr(cfg.settings, "google_oauth_client_id", "fake-client-id")
    monkeypatch.setattr(cfg.settings, "google_oauth_client_secret", "fake-secret")


async def _make_user(db_session) -> User:
    user = User(email="clarence@jarvis.ai", password_hash="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def test_authorization_url_contains_required_params():
    url = google_oauth.authorization_url(state="fake-state-token")

    assert "client_id=fake-client-id" in url
    assert "state=fake-state-token" in url
    assert "access_type=offline" in url


async def test_exchange_code_stores_encrypted_tokens(db_session):
    user = await _make_user(db_session)

    fake_response = httpx.Response(
        200,
        json={
            "access_token": "fake-access-token-xyz",
            "refresh_token": "fake-refresh-token-abc",
            "expires_in": 3600,
            "scope": "calendar.events gmail.send",
        },
        request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
    )

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        integration = await google_oauth.exchange_code(db_session, user, code="fake-auth-code")

    assert integration.provider == "google"
    assert "fake-access-token-xyz" not in integration.encrypted_access_token
    assert decrypt(integration.encrypted_access_token) == "fake-access-token-xyz"
    assert decrypt(integration.encrypted_refresh_token) == "fake-refresh-token-abc"


async def test_reconnecting_updates_existing_row_without_duplicating(db_session):
    user = await _make_user(db_session)

    fake_response = httpx.Response(
        200,
        json={"access_token": "token-1", "refresh_token": "refresh-1", "expires_in": 3600},
        request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
    )

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        await google_oauth.exchange_code(db_session, user, code="code-1")
        await google_oauth.exchange_code(db_session, user, code="code-2")

    count = await db_session.scalar(select(func.count()).select_from(Integration))
    assert count == 1


async def test_get_valid_access_token_refreshes_expired_token(db_session):
    user = await _make_user(db_session)

    initial_response = httpx.Response(
        200,
        json={"access_token": "old-token", "refresh_token": "refresh-abc", "expires_in": -10},
        request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=initial_response)):
        await google_oauth.exchange_code(db_session, user, code="initial-code")

    refresh_response = httpx.Response(
        200,
        json={"access_token": "brand-new-token", "expires_in": 3600},
        request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=refresh_response)):
        token = await google_oauth.get_valid_access_token(db_session, user)

    assert token == "brand-new-token"


async def test_get_valid_access_token_without_connection_raises_clear_error(db_session):
    user = await _make_user(db_session)

    with pytest.raises(google_oauth.GoogleIntegrationError):
        await google_oauth.get_valid_access_token(db_session, user)
