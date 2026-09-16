"""Mode texte — WebSocket `/api/v1/chat/ws`.

Réutilise exactement le même orchestrateur que le module vocal
(`app/ai/orchestrator.py`) : même mémoire, mêmes agents, mêmes outils.
Seule différence avec `voice.py` : pas de synthèse vocale de la réponse
(le mobile affiche le texte directement dans `ChatScreen`).
"""
import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.ai.orchestrator import get_or_create_conversation, process_turn
from app.core.security import decode_token
from app.database.session import AsyncSessionLocal
from app.models.user import User

router = APIRouter(prefix="/chat", tags=["chat"])


async def _authenticate_ws(websocket: WebSocket) -> User | None:
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
    async with AsyncSessionLocal() as db:
        conversation = await get_or_create_conversation(db, user, conversation_id, mode="text")
        result = await process_turn(db, user, conversation, user_text)

    await websocket.send_json({"type": "assistant_message", "text": result.text, "agent": result.agent_used})


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    user = await _authenticate_ws(websocket)
    if user is None:
        return

    async with AsyncSessionLocal() as db:
        conversation = await get_or_create_conversation(db, user, None, mode="text")
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

            if msg_type == "user_message":
                if current_task and not current_task.done():
                    current_task.cancel()

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
