"""Module vocal — endpoints WebSocket (conversation temps réel) et REST
(transcription de secours).

Flux nominal (voir mobile `voice_recognition_service.dart` + `voice_socket_service.dart`) :
1. Le mobile détecte le mot-clé "Jarvis" et transcrit localement la commande
   (speech_to_text, pour la latence et la confidentialité).
2. Le texte transcrit est envoyé sur `/api/v1/voice/ws` avec la langue détectée.
3. Le backend route la demande vers l'orchestrateur multi-agent (étape 5),
   synthétise la réponse en audio (ElevenLabs) et renvoie texte + audio (base64).
4. Un message `{"type": "cancel"}` interrompt la génération en cours
   (ex : l'utilisateur recommence à parler par-dessus la réponse).

Une conversation est créée à l'ouverture de la session WebSocket et
réutilisée pour tous les tours suivants — la mémoire court terme
(historique des messages) est donc conservée pendant toute la session.

Authentification : le token JWT est transmis en query param
(`?token=...`) car les clients WebSocket ne gèrent pas tous les headers
personnalisés facilement.
"""
import asyncio
import base64
import json
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, status

from app.ai.orchestrator import get_or_create_conversation, process_turn
from app.core.security import decode_token
from app.database.session import AsyncSessionLocal
from app.models.user import User
from app.services.stt_service import transcribe_audio
from app.services.tts_service import synthesize_speech

router = APIRouter(prefix="/voice", tags=["voice"])


async def _authenticate_ws(websocket: WebSocket) -> User | None:
    """Valide le token JWT passé en query param et charge l'utilisateur.
    Ferme la connexion et renvoie None si invalide."""
    token = websocket.query_params.get("token")
    payload = decode_token(token) if token else None
    if not payload or payload.get("type") != "access":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    async with AsyncSessionLocal() as db:
        user = await db.get(User, uuid.UUID(payload["sub"]))
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    return user


async def _handle_turn(websocket: WebSocket, user: User, conversation_id: uuid.UUID, user_text: str) -> None:
    """Traite un tour de conversation complet : orchestrateur multi-agent
    + synthèse vocale. Isolé dans une tâche annulable (voir /ws)."""
    async with AsyncSessionLocal() as db:
        conversation = await get_or_create_conversation(db, user, conversation_id, mode="voice")
        result = await process_turn(db, user, conversation, user_text)

    await websocket.send_json({"type": "assistant_text", "text": result.text, "agent": result.agent_used})

    try:
        audio_bytes = await synthesize_speech(result.text)
        await websocket.send_json(
            {
                "type": "assistant_audio",
                "format": "mp3",
                "audio_base64": base64.b64encode(audio_bytes).decode(),
            }
        )
    except HTTPException:
        # Pas de clé ElevenLabs configurée, ou service indisponible : le mobile
        # doit alors se rabattre sur sa synthèse vocale locale (flutter_tts).
        await websocket.send_json({"type": "assistant_audio_unavailable"})


@router.websocket("/ws")
async def voice_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    user = await _authenticate_ws(websocket)
    if user is None:
        return

    # Une conversation par session WebSocket — créée une seule fois à
    # l'ouverture, réutilisée pour tous les tours suivants (mémoire
    # court terme de la session).
    async with AsyncSessionLocal() as db:
        conversation = await get_or_create_conversation(db, user, None, mode="voice")
    conversation_id = conversation.id

    current_task: asyncio.Task | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Message JSON invalide."})
                continue

            msg_type = message.get("type")

            if msg_type == "cancel":
                if current_task and not current_task.done():
                    current_task.cancel()
                await websocket.send_json({"type": "cancelled"})
                continue

            if msg_type == "user_text":
                if current_task and not current_task.done():
                    current_task.cancel()  # une nouvelle commande annule la précédente

                text = (message.get("text") or "").strip()

                if not text:
                    await websocket.send_json({"type": "error", "detail": "Texte vide."})
                    continue

                current_task = asyncio.create_task(_handle_turn(websocket, user, conversation_id, text))
                continue

            await websocket.send_json({"type": "error", "detail": f"Type de message inconnu: {msg_type}"})

    except WebSocketDisconnect:
        if current_task and not current_task.done():
            current_task.cancel()


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = Form(default=None),
):
    """Transcription de secours : upload d'un fichier audio, renvoie le texte.
    À utiliser uniquement quand la reconnaissance vocale locale du mobile
    échoue (langue non supportée, environnement trop bruyant, etc.)."""
    audio_bytes = await file.read()
    text = await transcribe_audio(audio_bytes, file.filename or "audio.wav", language)
    return {"text": text}
