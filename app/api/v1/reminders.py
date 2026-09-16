"""Lecture des rappels créés par l'agent d'automatisation (étape 5) —
utilisé par le tableau de bord mobile (étape 9) pour afficher les
prochaines échéances sans repasser par une conversation."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.reminder import Reminder
from app.models.user import User

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("")
async def list_reminders(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Reminder)
        .where(Reminder.user_id == current_user.id, Reminder.status == "pending")
        .order_by(Reminder.due_at.asc())
        .limit(20)
    )
    reminders = result.scalars().all()

    return [
        {"id": str(r.id), "title": r.title, "due_at": r.due_at.isoformat(), "status": r.status}
        for r in reminders
    ]
