from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models import Notification, User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    r = await db.execute(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(100)
    )
    rows = r.scalars().all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "read_at": n.read_at.isoformat() if n.read_at else None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "payload": n.payload,
        }
        for n in rows
    ]


@router.delete("")
async def clear_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    await db.execute(delete(Notification).where(Notification.user_id == user.id))
    await db.commit()
    return Response(status_code=204)
