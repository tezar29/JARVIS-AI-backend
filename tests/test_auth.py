"""Tests d'intégration des endpoints d'authentification (étape 2).

Exécution : pytest tests/ -v
"""
import pytest


async def test_register_and_login(client):
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@jarvis.ai", "password": "supersecret123"},
    )
    assert register_resp.status_code == 201
    assert register_resp.json()["email"] == "test@jarvis.ai"

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@jarvis.ai", "password": "supersecret123"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens


async def test_register_duplicate_email_rejected(client):
    await client.post("/api/v1/auth/register", json={"email": "dup@jarvis.ai", "password": "supersecret123"})
    resp = await client.post("/api/v1/auth/register", json={"email": "dup@jarvis.ai", "password": "anotherpass1"})
    assert resp.status_code == 409


async def test_login_wrong_password_rejected(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "test2@jarvis.ai", "password": "supersecret123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test2@jarvis.ai", "password": "wrongpass"},
    )
    assert resp.status_code == 401


async def test_me_requires_authentication(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_returns_current_user(client):
    await client.post("/api/v1/auth/register", json={"email": "me@jarvis.ai", "password": "supersecret123"})
    login_resp = await client.post("/api/v1/auth/login", json={"email": "me@jarvis.ai", "password": "supersecret123"})
    access_token = login_resp.json()["access_token"]

    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@jarvis.ai"


async def test_refresh_issues_new_tokens(client):
    await client.post("/api/v1/auth/register", json={"email": "refresh@jarvis.ai", "password": "supersecret123"})
    login_resp = await client.post("/api/v1/auth/login", json={"email": "refresh@jarvis.ai", "password": "supersecret123"})
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_health_check(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
