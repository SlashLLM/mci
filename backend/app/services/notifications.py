from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


async def notify_user(
    db: AsyncSession,
    user_id: int,
    title: str,
    body: str,
    channel: str = "in_app",
    payload: Optional[dict[str, Any]] = None,
) -> Notification:
    n = Notification(
        user_id=user_id,
        title=title,
        body=body,
        channel=channel,
        payload=payload or {},
    )
    db.add(n)
    await db.flush()
    # Phase 2: enqueue FCM / email via Redis
    return n
