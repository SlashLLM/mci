from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import WorkerProfile
from app.services.recommendations import recompute_all_active_worker_recommendations, recompute_worker_recommendations

logger = logging.getLogger(__name__)
_queued_worker_ids: set[int] = set()


def enqueue_worker_recommendation_refresh(worker_profile_id: int) -> None:
    _queued_worker_ids.add(int(worker_profile_id))


async def process_recommendation_refresh_once() -> dict:
    """Run queued worker refreshes and periodic daily baseline refresh."""
    processed_workers = 0
    daily_refreshed = False
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        queued = sorted(_queued_worker_ids)
        _queued_worker_ids.clear()
        for worker_id in queued:
            worker = await db.get(WorkerProfile, worker_id)
            if not worker:
                continue
            await recompute_worker_recommendations(db, worker, source="post_shift")
            processed_workers += 1

        # Daily baseline refresh around 03:00 UTC.
        if now.hour == 3 and now.minute < 10:
            await recompute_all_active_worker_recommendations(db, source="daily")
            daily_refreshed = True
        await db.commit()
    return {"processed_workers": processed_workers, "daily_refreshed": daily_refreshed}


async def recommendation_refresh_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            outcome = await process_recommendation_refresh_once()
            if outcome["processed_workers"] or outcome["daily_refreshed"]:
                logger.info(
                    "recommendation_refresh processed_workers=%s daily_refreshed=%s",
                    outcome["processed_workers"],
                    outcome["daily_refreshed"],
                )
        except Exception:
            logger.exception("recommendation_refresh loop error")
        try:
            await asyncio.wait_for(stop.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            continue
