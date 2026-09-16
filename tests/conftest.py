"""Configuration pytest partagée à toute la suite de tests.

Les variables d'environnement doivent être fixées AVANT le premier
import d'un module `app.*` (la configuration Pydantic est lue une
seule fois, à l'import de `app.core.config`) — c'est pourquoi ce bloc
est tout en haut du fichier, avant les autres imports.

La suite tourne entièrement sur **SQLite en mémoire**, sans dépendance
à un vrai PostgreSQL : plus rapide, aucune infrastructure à démarrer
pour lancer `pytest`. Contrepartie assumée : les requêtes spécifiques à
pgvector (`cosine_distance`, recherche par similarité de la mémoire
long terme) ne sont pas exercées par cette suite — voir
`tests/test_memory_service.py` pour ce qui est couvert malgré tout
(écriture, dégradation gracieuse) et ce qui ne l'est pas.
"""
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use")
os.environ.setdefault("ENCRYPTION_KEY", "0" * 64)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — enregistre tous les modèles pour create_all
from app.database.session import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def db_session():
    """Base SQLite en mémoire fraîche pour chaque test, avec toutes les
    tables créées. `StaticPool` garde une unique connexion vivante
    pendant toute la durée du test — indispensable pour une base
    `:memory:`, qui sinon redémarrerait vide à chaque nouvelle connexion."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    async with session_factory() as session:
        yield session

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    """Client HTTP async contre l'app FastAPI réelle, base de test isolée."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
