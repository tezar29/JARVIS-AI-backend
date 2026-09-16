"""Point d'entrée de l'API JARVIS AI.

Lancement local : uvicorn app.main:app --reload
Lancement via Docker : voir docker-compose.yml
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, chat, health, integrations, reminders, vision, voice
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="API backend de l'assistant personnel JARVIS AI",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routeurs v1 — chaque nouveau module (voice, vision, memory, automation)
# ajoutera son propre routeur ici au fil des prochaines étapes.
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(voice.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(vision.router, prefix="/api/v1")
app.include_router(reminders.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "JARVIS AI — en ligne."}
