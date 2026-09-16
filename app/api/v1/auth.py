"""Endpoints d'authentification : inscription, connexion, rafraîchissement,
profil courant. La connexion biométrique (endpoint /biometric-login) est
volontairement laissée en TODO — elle nécessite l'enregistrement préalable
d'une clé publique par device, ajouté à l'étape "Sécurité avancée"."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import RefreshRequest, TokenPair, UserLogin, UserOut, UserRegister
from app.services.auth_service import (
    authenticate_user,
    issue_tokens,
    refresh_access_token,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await register_user(db, data)
    return user


@router.post("/login", response_model=TokenPair)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, data)
    return issue_tokens(user.id)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await refresh_access_token(db, data.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
