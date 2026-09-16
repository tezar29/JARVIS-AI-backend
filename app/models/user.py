"""Modèle ORM de l'utilisateur.

`biometric_public_key` stocke la clé publique correspondant à la clé
privée conservée dans l'enclave sécurisée du téléphone (Face ID /
empreinte) — la clé privée ne quitte jamais l'appareil ; le serveur
ne fait que vérifier une signature.
"""
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    biometric_public_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
