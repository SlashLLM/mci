"""Regression: draft job orders must not be forced to open by fill refresh."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from app.models import DispatchMode, JobOrder, JobOrderStatus, PayModel
from app.services.job_status import refresh_job_order_fill_status


def test_refresh_preserves_draft_when_unpublished():
    job = JobOrder(
        client_org_id=1,
        created_by_user_id=1,
        title="t",
        job_type="Warehouse Worker",
        location_address="addr",
        location_lat=1.35,
        location_lng=103.82,
        workers_required_total=2,
        pay_model=PayModel.hourly,
        dispatch_mode=DispatchMode.fcfs,
        status=JobOrderStatus.draft,
        published_at=None,
    )
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[2, 0])
    asyncio.run(refresh_job_order_fill_status(db, job))
    assert job.status == JobOrderStatus.draft
    assert db.scalar.await_count == 0


def test_refresh_updates_fill_when_published():
    job = JobOrder(
        client_org_id=1,
        created_by_user_id=1,
        title="t",
        job_type="Warehouse Worker",
        location_address="addr",
        location_lat=1.35,
        location_lng=103.82,
        workers_required_total=2,
        pay_model=PayModel.hourly,
        dispatch_mode=DispatchMode.fcfs,
        status=JobOrderStatus.open,
        published_at=datetime.now(timezone.utc),
    )
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[5, 2])
    asyncio.run(refresh_job_order_fill_status(db, job))
    assert job.status == JobOrderStatus.partially_filled
