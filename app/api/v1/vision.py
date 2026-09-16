"""Module de vision artificielle — `POST /api/v1/vision/analyze`.

Pas de WebSocket ici : l'analyse d'image est un échange ponctuel
(upload → résultat), contrairement au vocal/chat qui sont conversationnels
en continu. Le résultat est néanmoins persisté dans l'historique de la
conversation si un `conversation_id` est fourni, pour que le chat texte
ou vocal qui suit puisse s'y référer ("et sur cette photo, il y avait
écrit quoi déjà ?").

Ce endpoint n'est volontairement pas routé par l'orchestrateur
multi-agent (`ai/orchestrator.py`) : contrairement au texte, une image
n'a pas d'"intention" à classifier par mots-clés — sa seule présence
suffit à déterminer qu'il s'agit d'une demande de vision.
"""
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator import get_or_create_conversation, record_vision_exchange
from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.services.vision_service import VisionServiceError, analyze_image, validate_image

router = APIRouter(prefix="/vision", tags=["vision"])

VALID_MODES = {"describe", "ocr", "objects"}


@router.post("/analyze")
async def vision_analyze(
    file: UploadFile = File(...),
    mode: str = Form("describe"),
    question: str | None = Form(None),
    conversation_id: uuid.UUID | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if mode not in VALID_MODES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Mode invalide. Valeurs possibles : {', '.join(VALID_MODES)}.")

    image_bytes = await file.read()
    validate_image(file.content_type or "", len(image_bytes))

    try:
        result_text = await analyze_image(image_bytes, file.content_type, mode=mode, question=question)
    except VisionServiceError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    conversation = await get_or_create_conversation(db, current_user, conversation_id, mode="text")

    user_caption = question.strip() if question else f"[Image envoyée — mode: {mode}]"
    await record_vision_exchange(db, conversation, user_caption, result_text)

    return {
        "text": result_text,
        "mode": mode,
        "conversation_id": str(conversation.id),
    }
