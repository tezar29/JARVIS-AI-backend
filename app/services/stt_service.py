"""Service de reconnaissance vocale (Speech-to-Text) via l'API Whisper.

Utilisé en secours quand la reconnaissance vocale locale du téléphone
(speech_to_text côté Flutter) n'est pas disponible ou peu fiable
(bruit ambiant, langue rare, etc.) — endpoint REST dédié dans
`api/v1/voice.py`. Le flux principal (wake-word + STT en direct)
reste local sur l'appareil pour la latence et la confidentialité.
"""
import httpx
from fastapi import HTTPException, status

from app.core.config import settings

WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"


async def transcribe_audio(audio_bytes: bytes, filename: str, language: str | None = None) -> str:
    """Envoie un fichier audio à Whisper et renvoie le texte transcrit."""
    if not settings.openai_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Le service de transcription n'est pas configuré (clé OpenAI manquante).",
        )

    files = {"file": (filename, audio_bytes)}
    data = {"model": "whisper-1"}
    if language:
        data["language"] = language

    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(WHISPER_URL, headers=headers, data=data, files=files)

    if response.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Échec de la transcription audio.")

    return response.json()["text"]
