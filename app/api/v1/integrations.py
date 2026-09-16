"""Endpoints de connexion aux intégrations externes.

Flux Google (voir `integrations/google_oauth.py` pour le détail) :
1. Le mobile appelle `GET /integrations/google/connect` (authentifié) →
   reçoit une `auth_url`, l'ouvre dans un navigateur intégré (Custom Tabs /
   SFSafariViewController).
2. Après autorisation, Google redirige vers `/integrations/google/callback`.
3. Le callback échange le code, stocke les tokens chiffrés, et renvoie
   une page de confirmation simple.

Le `state` du flux OAuth transporte un JWT d'accès classique (même
mécanisme que l'authentification normale, voir `core/security.py`) :
c'est ce qui permet d'identifier l'utilisateur au moment du callback,
qui est un simple GET de navigateur sans header Authorization possible.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import create_access_token, decode_token
from app.database.session import AsyncSessionLocal, get_db
from app.integrations import google_oauth
from app.models.integration import Integration
from app.models.user import User

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/google/connect")
async def google_connect(current_user: User = Depends(get_current_user)):
    """Renvoie l'URL d'autorisation Google à ouvrir dans un navigateur
    intégré côté mobile. Un token signé de courte durée identifie
    l'utilisateur lors du callback (voir note ci-dessus)."""
    state_token = create_access_token(str(current_user.id))
    auth_url = google_oauth.authorization_url(state=state_token)
    return {"auth_url": auth_url}


@router.get("/google/callback")
async def google_callback(code: str = Query(...), state: str = Query(...)):
    """Callback OAuth appelé par Google après autorisation de l'utilisateur."""
    payload = decode_token(state)
    if not payload or payload.get("type") != "access":
        return HTMLResponse("<h3>Session expirée. Relance la connexion depuis l'application.</h3>", status_code=400)

    async with AsyncSessionLocal() as session:
        user = await session.get(User, uuid.UUID(payload["sub"]))
        if not user:
            return HTMLResponse("<h3>Utilisateur introuvable.</h3>", status_code=400)

        try:
            await google_oauth.exchange_code(session, user, code)
        except google_oauth.GoogleIntegrationError as exc:
            return HTMLResponse(f"<h3>Échec de la connexion à Google : {exc}</h3>", status_code=400)

    return HTMLResponse(
        "<h3>Compte Google connecté avec succès ✅</h3><p>Tu peux fermer cette fenêtre et revenir à JARVIS.</p>"
    )


@router.get("/status")
async def integrations_status(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Renvoie l'état des intégrations de l'utilisateur — utilisé par le
    mobile pour afficher "Google connecté ✅" / "Non connecté" dans les réglages."""
    result = await db.execute(select(Integration.provider).where(Integration.user_id == current_user.id))
    connected = [row[0] for row in result.all()]

    return {
        "google": "google" in connected,
        # WhatsApp est une config serveur (numéro professionnel partagé),
        # pas une connexion par utilisateur — voir whatsapp_service.py.
        "whatsapp": _whatsapp_configured(),
    }


def _whatsapp_configured() -> bool:
    from app.integrations.whatsapp_service import is_configured

    return is_configured()
