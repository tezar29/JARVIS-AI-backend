"""Service de vision artificielle — analyse d'images via le modèle
vision natif de Claude (Anthropic).

⚠️ Choix délibéré : contrairement à la conversation texte (routée sur
plusieurs fournisseurs, voir `ai/llm/router.py`), la vision n'est
implémentée qu'avec Claude ici. GPT-4o et Gemini savent aussi analyser
des images, mais ajouter une chaîne de secours multimodale complète
(avec la complexité de traduire des blocs image dans 3 formats natifs
différents) n'apporte pas assez de valeur à ce stade pour justifier la
complexité — Claude suffit largement pour l'usage visé. À réévaluer si
la résilience multi-fournisseur devient un besoin réel pour ce module.
"""
import base64

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
VISION_MODEL = "claude-sonnet-4-6"

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 Mo — cohérent avec les limites usuelles de l'API Anthropic
SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

_INSTRUCTIONS = {
    "describe": (
        "Décris cette image de façon claire et concise pour quelqu'un qui ne peut pas la voir : "
        "ce qu'elle montre, le contexte général, les éléments notables. 3-4 phrases suffisent "
        "sauf si l'utilisateur demande plus de détails."
    ),
    "ocr": (
        "Extrait tout le texte visible dans cette image, mot pour mot, en préservant autant que "
        "possible la mise en forme (lignes, paragraphes). Si aucun texte n'est visible, dis-le clairement."
    ),
    "objects": (
        "Liste les objets et éléments identifiables dans cette image, sous forme de liste à puces "
        "courte. Sois précis mais ne sur-interprète pas ce qui n'est pas clairement visible."
    ),
}


class VisionServiceError(Exception):
    pass


def validate_image(content_type: str, size: int) -> None:
    if content_type not in SUPPORTED_MEDIA_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Format d'image non supporté ({content_type}). Formats acceptés : {', '.join(SUPPORTED_MEDIA_TYPES)}.",
        )
    if size > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Image trop volumineuse (8 Mo max).")


async def analyze_image(image_bytes: bytes, media_type: str, mode: str = "describe", question: str | None = None) -> str:
    """Analyse une image avec Claude. `mode` choisit une instruction
    prédéfinie (describe/ocr/objects) ; `question`, si fourni, prend le
    dessus (analyse visuelle guidée par une question libre de
    l'utilisateur, ex: "est-ce que j'ai laissé mes clés sur la table ?")."""
    if not settings.anthropic_api_key:
        raise VisionServiceError("Le module de vision nécessite une clé API Anthropic configurée (ANTHROPIC_API_KEY).")

    instruction = question.strip() if question and question.strip() else _INSTRUCTIONS.get(mode, _INSTRUCTIONS["describe"])

    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": VISION_MODEL,
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.b64encode(image_bytes).decode(),
                        },
                    },
                    {"type": "text", "text": instruction},
                ],
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(ANTHROPIC_URL, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise VisionServiceError(f"Service de vision injoignable: {exc}") from exc

    if response.status_code != 200:
        raise VisionServiceError(f"Échec de l'analyse d'image: {response.status_code} {response.text}")

    data = response.json()
    text_parts = [block["text"] for block in data.get("content", []) if block["type"] == "text"]
    return "".join(text_parts) or "Je n'ai pas réussi à extraire d'information de cette image."
