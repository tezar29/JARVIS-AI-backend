"""Mémoire long terme de JARVIS — indexation et recherche par
similarité vectorielle (RAG), au-dessus de pgvector.

Complète la mémoire court terme de l'orchestrateur (derniers messages
de la conversation en cours) : ici, les souvenirs survivent à la
conversation et sont retrouvés par pertinence sémantique plutôt que
par ordre chronologique — c'est ce qui permet à JARVIS d'apprendre
progressivement les habitudes de l'utilisateur au fil du temps.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.memory.embedding_service import EmbeddingServiceUnavailable, get_embedding
from app.models.memory import MemoryEmbedding, MemoryItem
from app.models.user import User

logger = logging.getLogger("jarvis.memory")

DEFAULT_TOP_K = 5
# Distance cosinus max pour qu'un souvenir soit considéré pertinent
# (0 = identique, 2 = opposé). Évite de remonter du bruit non lié.
MAX_RELEVANT_DISTANCE = 0.5


async def remember(db: AsyncSession, user: User, content: str, category: str = "fact") -> MemoryItem | None:
    """Indexe un nouveau souvenir. Renvoie None (sans lever d'exception)
    si le service d'embeddings n'est pas disponible — la mémoire long
    terme est une amélioration, pas une dépendance critique."""
    try:
        vector = await get_embedding(content)
    except EmbeddingServiceUnavailable as exc:
        logger.warning("Impossible d'indexer le souvenir (embeddings indisponibles): %s", exc)
        return None

    item = MemoryItem(user_id=user.id, category=category, content=content)
    db.add(item)
    await db.flush()  # obtient item.id sans committer

    db.add(MemoryEmbedding(memory_item_id=item.id, embedding=vector))
    await db.commit()
    await db.refresh(item)
    return item


async def search_relevant_memories(db: AsyncSession, user: User, query_text: str, top_k: int = DEFAULT_TOP_K) -> list[str]:
    """Recherche les souvenirs les plus pertinents pour la requête
    donnée. Renvoie une liste vide (sans exception) si la mémoire long
    terme est indisponible ou si rien d'assez pertinent n'est trouvé."""
    try:
        query_vector = await get_embedding(query_text)
    except EmbeddingServiceUnavailable as exc:
        logger.warning("Recherche mémoire ignorée (embeddings indisponibles): %s", exc)
        return []

    distance = MemoryEmbedding.embedding.cosine_distance(query_vector)
    stmt = (
        select(MemoryItem.content, distance.label("distance"))
        .join(MemoryEmbedding, MemoryEmbedding.memory_item_id == MemoryItem.id)
        .where(MemoryItem.user_id == user.id)
        .order_by(distance)
        .limit(top_k)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [content for content, dist in rows if dist <= MAX_RELEVANT_DISTANCE]
