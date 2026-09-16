"""Schémas de requête/réponse pour les endpoints d'authentification."""
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class BiometricLogin(BaseModel):
    """Connexion via biométrie : le mobile envoie une signature produite
    par la clé privée de l'enclave sécurisée ; le serveur la vérifie avec
    la clé publique enregistrée."""
    user_id: uuid.UUID
    challenge: str
    signature: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    phone: str | None = None
