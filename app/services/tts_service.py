"""Service de synthèse vocale (Text-to-Speech) via ElevenLabs.

Renvoie des octets MP3 prêts à être encodés en base64 et transmis au
mobile sur la connexion WebSocket (voir `api/v1/voice.py`).
"""
import httpx
from fastapi import HTTPException, status

from app.core.config import settings

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# Voix par défaut (à remplacer par une voix personnalisée créée dans ElevenLabs).
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"


async def synthesize_speech(text: str, voice_id: str = DEFAULT_VOICE_ID) -> bytes:
    """Convertit du texte en audio MP3. Lève une exception HTTP si le
    service n'est pas configuré ou indisponible — l'appelant doit
    prévoir un repli sur la synthèse vocale locale du téléphone."""
    if not settings.elevenlabs_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Le service de synthèse vocale n'est pas configuré (clé ElevenLabs manquante).",
        )

    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",  # supporte le multilingue
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    url = ELEVENLABS_URL.format(voice_id=voice_id)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Échec de la synthèse vocale.")

    return response.content
