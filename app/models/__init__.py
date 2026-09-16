"""Registre central des modèles ORM — importé par Alembic pour
générer les migrations automatiquement (autogenerate)."""
from app.models.conversation import Conversation, Message  # noqa: F401
from app.models.integration import Integration  # noqa: F401
from app.models.memory import MemoryEmbedding, MemoryItem  # noqa: F401
from app.models.reminder import Reminder  # noqa: F401
from app.models.user import User  # noqa: F401
