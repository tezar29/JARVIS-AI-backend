"""Tests de la mémoire long terme (app/ai/memory/memory_service.py, étape 6).

Note de portée : la recherche par similarité cosinus (`search_relevant_memories`)
s'appuie sur l'opérateur pgvector `<=>`, spécifique à PostgreSQL — non
exercée ici (suite SQLite, voir conftest.py). Ce qui est couvert :
l'écriture réelle d'un souvenir et la dégradation gracieuse sans
service d'embeddings configuré, sur les deux fonctions publiques.
"""
import pytest
from sqlalchemy import select

from app.ai.memory import memory_service
from app.models.memory import MemoryEmbedding, MemoryItem
from app.models.user import User



async def _make_user(db_session) -> User:
    user = User(email="clarence@jarvis.ai", password_hash="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_remember_without_embeddings_configured_degrades_gracefully(db_session):
    user = await _make_user(db_session)

    item = await memory_service.remember(db_session, user, "Aime le thé, pas le café")

    assert item is None  # pas de clé OpenAI dans l'environnement de test
    items = (await db_session.execute(select(MemoryItem))).scalars().all()
    assert items == []


async def test_search_without_embeddings_configured_returns_empty_list(db_session):
    user = await _make_user(db_session)

    results = await memory_service.search_relevant_memories(db_session, user, "Quelle boisson aime Clarence ?")

    assert results == []


async def test_remember_writes_item_and_embedding_when_configured(db_session, monkeypatch):
    user = await _make_user(db_session)

    async def fake_get_embedding(text):
        return [0.1] * 1536

    monkeypatch.setattr(memory_service, "get_embedding", fake_get_embedding)

    item = await memory_service.remember(db_session, user, "Préfère les réunions le matin", category="preference")

    assert item is not None
    assert item.category == "preference"

    items = (await db_session.execute(select(MemoryItem))).scalars().all()
    embeddings = (await db_session.execute(select(MemoryEmbedding))).scalars().all()
    assert len(items) == 1
    assert len(embeddings) == 1
    assert len(embeddings[0].embedding) == 1536
