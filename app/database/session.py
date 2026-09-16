"""
Configuration de la connexion PostgreSQL en mode asynchrone.

Toutes les routes API reçoivent une session via la dépendance FastAPI
`get_db`, garantissant que la session est proprement fermée après
chaque requête (même en cas d'exception).
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.async_database_url, echo=settings.debug, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Classe de base commune à tous les modèles ORM."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
