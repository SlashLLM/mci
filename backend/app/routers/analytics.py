from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.services.analytics_reporting import (
    AnalyticsBucket,
    build_portal_dashboard,
    resolve_analytics_scope,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/portal-dashboard")
async def portal_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin, UserRole.client))],
    period_days: Annotated[int, Query(ge=30, le=365)] = 90,
    bucket: AnalyticsBucket = "week",
    client_org_id: int | None = None,
):
    scope = await resolve_analytics_scope(db, user, client_org_id)
    return await build_portal_dashboard(db, scope, period_days=period_days, bucket=bucket)


@router.get("/dashboard")
async def dashboard_kpis(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
    client_org_id: int | None = None,
):
    scope = await resolve_analytics_scope(db, user, client_org_id)
    dashboard = await build_portal_dashboard(db, scope, period_days=90, bucket="week")
    summary = dashboard["summary"]
    demand_supply_points = dashboard["demand_supply"]["points"]
    incident_points = dashboard["incident_trends"]["points"]
    total_slots = sum(int(point["total_slots"]) for point in dashboard["fill_rate_breakdowns"]["by_period"])
    confirmed_assignments = sum(int(point["filled_slots"]) for point in dashboard["fill_rate_breakdowns"]["by_period"])
    no_show_assignments = sum(int(point["no_shows"]) for point in incident_points)
    late_cancellations = sum(int(point["late_cancellations"]) for point in incident_points)
    return {
        "active_workers": int(summary["active_workers"]),
        "open_job_orders": int(summary["active_job_orders"]),
        "upcoming_shifts": int(summary["upcoming_shifts"]),
        "aggregate_fill_rate": float(summary["fill_rate"]),
        "confirmed_assignments": int(confirmed_assignments),
        "total_shift_slots": int(total_slots),
        "no_show_assignments": int(no_show_assignments),
        "late_cancellations": int(late_cancellations),
        "bucket_count": len(demand_supply_points),
    }


@router.get("/fill-rate-by-job-type")
async def fill_rate_by_job_type(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
    client_org_id: int | None = None,
):
    scope = await resolve_analytics_scope(db, user, client_org_id)
    dashboard = await build_portal_dashboard(db, scope, period_days=90, bucket="week")
    return {
        row["job_type"]: row["fill_rate"]
        for row in dashboard["fill_rate_breakdowns"]["by_job_type"]
    }
