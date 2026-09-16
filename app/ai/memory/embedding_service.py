"""Service de génération d'embeddings — utilisé pour indexer et
rechercher dans la mémoire long terme (RAG).

Utilise l'API d'embeddings d'OpenAI (`text-embedding-3-small`, 1536
dimensions) : c'est le fournisseur le plus simple et le moins cher pour
ça, indépendamment du LLM conversationnel choisi (Claude reste le LLM
principal — les embeddings sont un besoin technique séparé). Si aucune
clé OpenAI n'est configurée, la mémoire long terme est simplement
désactivée (dégradation gracieuse : JARVIS continue de fonctionner
avec la seule mémoire court terme de la conversation en cours).
"""
import httpx

from app.core.config import settings

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
EMBEDDING_MODEL = "text-embedding-3-small"


class EmbeddingServiceUnavailable(Exception):
    """Levée quand la génération d'embeddings n'est pas possible
    (clé absente ou API injoignable) — à intercepter pour dégrader
    gracieusement plutôt que faire échouer toute la conversation."""


def is_embedding_configured() -> bool:
    return bool(settings.openai_api_key)


async def get_embedding(text: str) -> list[float]:
    if not is_embedding_configured():
        raise EmbeddingServiceUnavailable("Clé API OpenAI manquante (nécessaire pour les embeddings).")

    headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}
    payload = {"model": EMBEDDING_MODEL, "input": text}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(OPENAI_EMBEDDINGS_URL, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise EmbeddingServiceUnavailable(f"Service d'embeddings injoignable: {exc}") from exc

    if response.status_code != 200:
        raise EmbeddingServiceUnavailable(f"Échec de génération d'embedding: {response.status_code}")

    return response.json()["data"][0]["embedding"]
