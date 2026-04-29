from __future__ import annotations

import asyncio
import logging

from app.db.session import AsyncSessionLocal
from app.services.dispatch import process_dispatch_tasks_once

logger = logging.getLogger(__name__)


async def dispatch_tasks_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            async with AsyncSessionLocal() as db:
                processed = await process_dispatch_tasks_once(db)
                await db.commit()
            if processed:
                logger.info("dispatch_tasks processed=%s", processed)
        except Exception:
            logger.exception("dispatch_tasks loop error")
        try:
            await asyncio.wait_for(stop.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            continue
