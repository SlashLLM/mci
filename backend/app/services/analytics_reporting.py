from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import fmean
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssignmentStatus,
    ClientOrganization,
    JobOrder,
    JobOrderStatus,
    Notification,
    Rating,
    Shift,
    ShiftAssignment,
    TimesheetEntry,
    User,
    UserRole,
    WorkerProfile,
    WorkerStatus,
)
from app.services.ta_client_contracts import list_contracted_org_ids_for_ta

AnalyticsBucket = Literal["day", "week", "month"]

ACTIVE_JOB_STATUSES = {
    JobOrderStatus.open,
    JobOrderStatus.partially_filled,
    JobOrderStatus.fully_filled,
}
STAFFED_ASSIGNMENT_STATUSES = {
    AssignmentStatus.confirmed,
    AssignmentStatus.completed,
    AssignmentStatus.no_show,
}
SCHEDULED_ASSIGNMENT_STATUSES = STAFFED_ASSIGNMENT_STATUSES | {AssignmentStatus.cancelled}


@dataclass
class AnalyticsScope:
    role: str
    org_ids: list[int]
    selected_client_org_id: int | None
    available_clients: list[dict[str, object]]


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _bucket_floor(dt: datetime, bucket: AnalyticsBucket) -> datetime:
    dt = _ensure_utc(dt)
    if bucket == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket == "week":
        start = dt - timedelta(days=dt.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _bucket_next(dt: datetime, bucket: AnalyticsBucket) -> datetime:
    if bucket == "day":
        return dt + timedelta(days=1)
    if bucket == "week":
        return dt + timedelta(days=7)
    year = dt.year + (1 if dt.month == 12 else 0)
    month = 1 if dt.month == 12 else dt.month + 1
    return dt.replace(year=year, month=month, day=1)


def _bucket_label(dt: datetime, bucket: AnalyticsBucket) -> str:
    if bucket == "day":
        return dt.strftime("%b %d")
    if bucket == "week":
        return f"Week of {dt.strftime('%b %d')}"
    return dt.strftime("%b %Y")


def _iter_buckets(start: datetime, end: datetime, bucket: AnalyticsBucket) -> list[datetime]:
    cur = _bucket_floor(start, bucket)
    limit = _bucket_floor(end, bucket)
    out: list[datetime] = []
    while cur <= limit:
        out.append(cur)
        cur = _bucket_next(cur, bucket)
    return out


def _series_slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(values) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
    den = sum((x - x_mean) ** 2 for x in xs)
    return num / den if den else 0.0


def _season_key(dt: datetime, bucket: AnalyticsBucket) -> int:
    if bucket == "day":
        return dt.weekday()
    if bucket == "week":
        return dt.month
    return dt.month


def _safe_rate(num: float, den: float) -> float:
    if not den:
        return 0.0
    return round(num / den, 4)


async def resolve_analytics_scope(
    db: AsyncSession,
    user: User,
    client_org_id: int | None,
) -> AnalyticsScope:
    if user.role == UserRole.client:
        if not user.client_org_id:
            raise HTTPException(status_code=400, detail="Client account is not linked to an organization")
        org = await db.get(ClientOrganization, user.client_org_id)
        if org is None:
            raise HTTPException(status_code=404, detail="Client organization not found")
        return AnalyticsScope(
            role=user.role.value,
            org_ids=[org.id],
            selected_client_org_id=org.id,
            available_clients=[{"id": org.id, "name": org.name}],
        )

    if user.role == UserRole.ta:
        allowed_ids = sorted(await list_contracted_org_ids_for_ta(db, user.id))
        if client_org_id is not None and client_org_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Client is outside your contracted analytics scope")
        target_ids = [client_org_id] if client_org_id is not None else allowed_ids
        if not target_ids:
            return AnalyticsScope(role=user.role.value, org_ids=[], selected_client_org_id=None, available_clients=[])
        rows = await db.execute(
            select(ClientOrganization.id, ClientOrganization.name).where(ClientOrganization.id.in_(allowed_ids))
        )
        clients = [{"id": row.id, "name": row.name} for row in rows]
        return AnalyticsScope(
            role=user.role.value,
            org_ids=target_ids,
            selected_client_org_id=client_org_id,
            available_clients=clients,
        )

    if user.role == UserRole.admin:
        stmt = select(ClientOrganization.id, ClientOrganization.name)
        if client_org_id is not None:
            stmt = stmt.where(ClientOrganization.id == client_org_id)
        rows = await db.execute(stmt.order_by(ClientOrganization.name.asc()))
        clients = [{"id": row.id, "name": row.name} for row in rows]
        return AnalyticsScope(
            role=user.role.value,
            org_ids=[row["id"] for row in clients],
            selected_client_org_id=client_org_id,
            available_clients=clients,
        )

    raise HTTPException(status_code=403, detail="Analytics access is not allowed for this role")


async def build_portal_dashboard(
    db: AsyncSession,
    scope: AnalyticsScope,
    *,
    period_days: int = 90,
    bucket: AnalyticsBucket = "week",
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    period_days = max(30, min(period_days, 365))
    range_start = now - timedelta(days=period_days)
    history_start = now - timedelta(days=max(period_days, 365))

    if not scope.org_ids:
        buckets = _iter_buckets(range_start, now, bucket)
        empty_points = [
            {
                "bucket_start": item.isoformat(),
                "label": _bucket_label(item, bucket),
                "job_orders": 0,
                "required_workers": 0,
                "filled_workers": 0,
                "open_positions": 0,
                "available_workers": 0,
                "fill_rate": 0.0,
            }
            for item in buckets
        ]
        return {
            "scope": {
                "role": scope.role,
                "client_org_ids": scope.org_ids,
                "selected_client_org_id": scope.selected_client_org_id,
                "available_clients": scope.available_clients,
            },
            "filters": {
                "period_days": period_days,
                "bucket": bucket,
                "generated_at": now.isoformat(),
            },
            "summary": {
                "active_workers": 0,
                "active_job_orders": 0,
                "fill_rate": 0.0,
                "open_positions": 0,
                "upcoming_shifts": 0,
            },
            "demand_supply": {"points": empty_points},
            "fill_rate_breakdowns": {
                "by_job_type": [],
                "by_client": [],
                "by_period": [
                    {
                        "bucket_start": point["bucket_start"],
                        "label": point["label"],
                        "filled_slots": 0,
                        "total_slots": 0,
                        "fill_rate": 0.0,
                    }
                    for point in empty_points
                ],
            },
            "worker_performance": {
                "summary": {"completion_rate": 0.0, "average_rating": 0.0, "no_show_rate": 0.0},
                "workers": [],
            },
            "incident_trends": {
                "points": [
                    {
                        "bucket_start": point["bucket_start"],
                        "label": point["label"],
                        "scheduled_assignments": 0,
                        "no_shows": 0,
                        "late_cancellations": 0,
                        "no_show_rate": 0.0,
                        "late_cancellation_rate": 0.0,
                    }
                    for point in empty_points
                ]
            },
            "payroll_summary": {
                "totals": {"hours_worked": 0.0, "gross_pay": 0.0},
                "by_period": [
                    {
                        "bucket_start": point["bucket_start"],
                        "label": point["label"],
                        "hours_worked": 0.0,
                        "gross_pay": 0.0,
                    }
                    for point in empty_points
                ],
                "by_client": [],
            },
            "forecast": {"basis_bucket": bucket, "points": [], "assumption": "Forecast unavailable without scoped history."},
            "retention_cohorts": {"period_labels": [], "cohorts": []},
        }

    job_rows = (
        await db.execute(
            select(
                JobOrder.id.label("job_id"),
                JobOrder.client_org_id,
                JobOrder.job_type,
                JobOrder.status,
                JobOrder.created_at,
                ClientOrganization.name.label("client_name"),
            )
            .join(ClientOrganization, ClientOrganization.id == JobOrder.client_org_id)
            .where(JobOrder.client_org_id.in_(scope.org_ids))
        )
    ).mappings().all()

    shift_rows = (
        await db.execute(
            select(
                Shift.id.label("shift_id"),
                Shift.job_order_id,
                Shift.starts_at,
                Shift.ends_at,
                Shift.workers_required,
                JobOrder.client_org_id,
                JobOrder.job_type,
                JobOrder.status.label("job_status"),
                ClientOrganization.name.label("client_name"),
            )
            .join(JobOrder, JobOrder.id == Shift.job_order_id)
            .join(ClientOrganization, ClientOrganization.id == JobOrder.client_org_id)
            .where(JobOrder.client_org_id.in_(scope.org_ids))
        )
    ).mappings().all()

    assignment_rows = (
        await db.execute(
            select(
                ShiftAssignment.id.label("assignment_id"),
                ShiftAssignment.shift_id,
                ShiftAssignment.worker_id,
                ShiftAssignment.status,
                Shift.starts_at,
                Shift.job_order_id,
                JobOrder.client_org_id,
                JobOrder.job_type,
                ClientOrganization.name.label("client_name"),
            )
            .join(Shift, Shift.id == ShiftAssignment.shift_id)
            .join(JobOrder, JobOrder.id == Shift.job_order_id)
            .join(ClientOrganization, ClientOrganization.id == JobOrder.client_org_id)
            .where(JobOrder.client_org_id.in_(scope.org_ids))
        )
    ).mappings().all()

    timesheet_rows = (
        await db.execute(
            select(
                TimesheetEntry.id.label("timesheet_id"),
                TimesheetEntry.worker_id,
                TimesheetEntry.actual_hours,
                TimesheetEntry.scheduled_hours,
                TimesheetEntry.gross_pay,
                Shift.starts_at,
                JobOrder.client_org_id,
                ClientOrganization.name.label("client_name"),
            )
            .join(Shift, Shift.id == TimesheetEntry.shift_id)
            .join(JobOrder, JobOrder.id == TimesheetEntry.job_order_id)
            .join(ClientOrganization, ClientOrganization.id == JobOrder.client_org_id)
            .where(JobOrder.client_org_id.in_(scope.org_ids))
        )
    ).mappings().all()

    rating_rows = (
        await db.execute(
            select(
                Rating.worker_id,
                Rating.stars,
                Shift.starts_at,
                JobOrder.client_org_id,
            )
            .join(ShiftAssignment, ShiftAssignment.id == Rating.shift_assignment_id)
            .join(Shift, Shift.id == ShiftAssignment.shift_id)
            .join(JobOrder, JobOrder.id == Shift.job_order_id)
            .where(JobOrder.client_org_id.in_(scope.org_ids))
        )
    ).mappings().all()

    worker_ids = sorted({int(row["worker_id"]) for row in assignment_rows})
    worker_rows = []
    if worker_ids:
        worker_rows = (
            await db.execute(
                select(
                    WorkerProfile.id,
                    WorkerProfile.full_name,
                    WorkerProfile.rating_avg,
                    WorkerProfile.completion_rate,
                    WorkerProfile.no_show_count,
                    WorkerProfile.late_cancel_count,
                    WorkerProfile.status,
                    WorkerProfile.created_at,
                ).where(WorkerProfile.id.in_(worker_ids))
            )
        ).mappings().all()

    notification_rows = (
        await db.execute(
            select(Notification.created_at, Notification.payload).where(Notification.created_at >= history_start)
        )
    ).mappings().all()

    jobs = [
        {
            **dict(row),
            "created_at": _ensure_utc(row["created_at"]),
        }
        for row in job_rows
    ]
    shifts = [
        {
            **dict(row),
            "starts_at": _ensure_utc(row["starts_at"]),
            "ends_at": _ensure_utc(row["ends_at"]),
        }
        for row in shift_rows
    ]
    assignments = [
        {
            **dict(row),
            "starts_at": _ensure_utc(row["starts_at"]),
        }
        for row in assignment_rows
    ]
    timesheets = [
        {
            **dict(row),
            "starts_at": _ensure_utc(row["starts_at"]),
        }
        for row in timesheet_rows
    ]
    ratings = [
        {
            **dict(row),
            "starts_at": _ensure_utc(row["starts_at"]),
        }
        for row in rating_rows
    ]
    workers = {int(row["id"]): dict(row) for row in worker_rows}
    shift_lookup = {int(row["shift_id"]): row for row in shifts}
    assignment_lookup = {int(row["assignment_id"]): row for row in assignments}

    late_cancel_events: dict[int, datetime] = {}
    for row in notification_rows:
        payload = row["payload"] or {}
        if payload.get("type") != "late_cancellation":
            continue
        assignment_id = payload.get("assignment_id")
        shift_id = payload.get("shift_id")
        if not isinstance(assignment_id, int) or not isinstance(shift_id, int):
            continue
        if shift_id not in shift_lookup:
            continue
        late_cancel_events[assignment_id] = _ensure_utc(row["created_at"])

    period_buckets = _iter_buckets(range_start, now, bucket)
    bucket_points: dict[datetime, dict[str, object]] = {
        item: {
            "bucket_start": item.isoformat(),
            "label": _bucket_label(item, bucket),
            "job_orders": set(),
            "required_workers": 0,
            "filled_workers": 0,
            "open_positions": 0,
            "available_workers": 0,
            "scheduled_assignments": 0,
            "no_shows": 0,
            "late_cancellations": 0,
            "hours_worked": 0.0,
            "gross_pay": 0.0,
        }
        for item in period_buckets
    }

    engaged_active_workers: set[int] = set()
    worker_first_seen: dict[int, datetime] = {}
    for row in assignments:
        worker_id = int(row["worker_id"])
        status = row["status"]
        starts_at = row["starts_at"]
        if status in STAFFED_ASSIGNMENT_STATUSES and worker_id in workers:
            if workers[worker_id]["status"] == WorkerStatus.active:
                worker_first_seen[worker_id] = min(worker_first_seen.get(worker_id, starts_at), starts_at)
        if starts_at < range_start or starts_at > now:
            continue
        bucket_start = _bucket_floor(starts_at, bucket)
        point = bucket_points.get(bucket_start)
        if point is None:
            continue
        point["scheduled_assignments"] = int(point["scheduled_assignments"]) + (
            1 if status in SCHEDULED_ASSIGNMENT_STATUSES else 0
        )
        if status in STAFFED_ASSIGNMENT_STATUSES:
            point["filled_workers"] = int(point["filled_workers"]) + 1
            if worker_id in workers and workers[worker_id]["status"] == WorkerStatus.active:
                engaged_active_workers.add(worker_id)
        if status == AssignmentStatus.no_show:
            point["no_shows"] = int(point["no_shows"]) + 1

    for worker_id, first_seen in worker_first_seen.items():
        for item in period_buckets:
            if first_seen <= _bucket_next(item, bucket):
                bucket_points[item]["available_workers"] = int(bucket_points[item]["available_workers"]) + 1

    for row in shifts:
        starts_at = row["starts_at"]
        if starts_at < range_start or starts_at > now:
            continue
        bucket_start = _bucket_floor(starts_at, bucket)
        point = bucket_points.get(bucket_start)
        if point is None:
            continue
        point["job_orders"].add(int(row["job_order_id"]))
        point["required_workers"] = int(point["required_workers"]) + int(row["workers_required"] or 0)

    for assignment_id, event_dt in late_cancel_events.items():
        assignment = assignment_lookup.get(assignment_id)
        if assignment is None:
            continue
        if event_dt < range_start or event_dt > now:
            continue
        bucket_start = _bucket_floor(event_dt, bucket)
        point = bucket_points.get(bucket_start)
        if point is not None:
            point["late_cancellations"] = int(point["late_cancellations"]) + 1

    for row in timesheets:
        starts_at = row["starts_at"]
        if starts_at < range_start or starts_at > now:
            continue
        bucket_start = _bucket_floor(starts_at, bucket)
        point = bucket_points.get(bucket_start)
        if point is None:
            continue
        hours = float(row["actual_hours"] or row["scheduled_hours"] or 0.0)
        point["hours_worked"] = float(point["hours_worked"]) + hours
        point["gross_pay"] = float(point["gross_pay"]) + float(row["gross_pay"] or 0.0)

    demand_supply_points = []
    fill_rate_by_period = []
    incident_points = []
    payroll_periods = []
    total_slots_period = 0
    total_filled_period = 0
    total_hours_period = 0.0
    total_pay_period = 0.0
    for item in period_buckets:
        point = bucket_points[item]
        required_workers = int(point["required_workers"])
        filled_workers = int(point["filled_workers"])
        scheduled_assignments = int(point["scheduled_assignments"])
        no_shows = int(point["no_shows"])
        late_cancellations = int(point["late_cancellations"])
        demand_supply_points.append(
            {
                "bucket_start": point["bucket_start"],
                "label": point["label"],
                "job_orders": len(point["job_orders"]),
                "required_workers": required_workers,
                "filled_workers": filled_workers,
                "open_positions": max(0, required_workers - filled_workers),
                "available_workers": int(point["available_workers"]),
                "fill_rate": _safe_rate(filled_workers, required_workers),
            }
        )
        fill_rate_by_period.append(
            {
                "bucket_start": point["bucket_start"],
                "label": point["label"],
                "filled_slots": filled_workers,
                "total_slots": required_workers,
                "fill_rate": _safe_rate(filled_workers, required_workers),
            }
        )
        incident_points.append(
            {
                "bucket_start": point["bucket_start"],
                "label": point["label"],
                "scheduled_assignments": scheduled_assignments,
                "no_shows": no_shows,
                "late_cancellations": late_cancellations,
                "no_show_rate": _safe_rate(no_shows, scheduled_assignments),
                "late_cancellation_rate": _safe_rate(late_cancellations, scheduled_assignments),
            }
        )
        hours_worked = round(float(point["hours_worked"]), 2)
        gross_pay = round(float(point["gross_pay"]), 2)
        payroll_periods.append(
            {
                "bucket_start": point["bucket_start"],
                "label": point["label"],
                "hours_worked": hours_worked,
                "gross_pay": round(gross_pay, 2),
            }
        )
        total_slots_period += required_workers
        total_filled_period += filled_workers
        total_hours_period += hours_worked
        total_pay_period += gross_pay

    future_shifts = [
        row
        for row in shifts
        if row["starts_at"] > now and row["job_status"] in ACTIVE_JOB_STATUSES
    ]
    current_active_job_orders = {
        int(row["job_id"]) for row in jobs if row["status"] in ACTIVE_JOB_STATUSES
    }
    staffing_counts_by_shift: dict[int, int] = defaultdict(int)
    for row in assignments:
        if row["status"] in STAFFED_ASSIGNMENT_STATUSES:
            staffing_counts_by_shift[int(row["shift_id"])] += 1
    open_positions = sum(
        max(0, int(row["workers_required"] or 0) - staffing_counts_by_shift.get(int(row["shift_id"]), 0))
        for row in shifts
        if row["ends_at"] >= now and row["job_status"] in ACTIVE_JOB_STATUSES
    )

    by_job_type: dict[str, dict[str, float]] = defaultdict(lambda: {"slots": 0, "filled": 0})
    by_client: dict[str, dict[str, float | int | str]] = defaultdict(
        lambda: {"slots": 0, "filled": 0, "client_name": "", "client_org_id": 0}
    )
    shift_required_lookup = {int(row["shift_id"]): int(row["workers_required"] or 0) for row in shifts}
    shift_window_ids = {
        int(row["shift_id"]) for row in shifts if range_start <= row["starts_at"] <= now
    }
    for row in shifts:
        if int(row["shift_id"]) not in shift_window_ids:
            continue
        by_job_type[row["job_type"]]["slots"] += int(row["workers_required"] or 0)
        client_bucket = by_client[row["client_name"]]
        client_bucket["slots"] += int(row["workers_required"] or 0)
        client_bucket["client_name"] = row["client_name"]
        client_bucket["client_org_id"] = int(row["client_org_id"])
    for row in assignments:
        if row["status"] not in STAFFED_ASSIGNMENT_STATUSES or int(row["shift_id"]) not in shift_window_ids:
            continue
        by_job_type[row["job_type"]]["filled"] += 1
        client_bucket = by_client[row["client_name"]]
        client_bucket["filled"] += 1

    worker_stats: dict[int, dict[str, object]] = {}
    worker_ratings: dict[int, list[int]] = defaultdict(list)
    for rating in ratings:
        if range_start <= rating["starts_at"] <= now:
            worker_ratings[int(rating["worker_id"])].append(int(rating["stars"]))
    for row in assignments:
        worker_id = int(row["worker_id"])
        if worker_id not in workers or not (range_start <= row["starts_at"] <= now):
            continue
        stat = worker_stats.setdefault(
            worker_id,
            {
                "worker_id": worker_id,
                "worker_name": workers[worker_id]["full_name"],
                "completed_shifts": 0,
                "scheduled_assignments": 0,
                "no_shows": 0,
                "late_cancellations": 0,
            },
        )
        if row["status"] in SCHEDULED_ASSIGNMENT_STATUSES:
            stat["scheduled_assignments"] = int(stat["scheduled_assignments"]) + 1
        if row["status"] == AssignmentStatus.completed:
            stat["completed_shifts"] = int(stat["completed_shifts"]) + 1
        if row["status"] == AssignmentStatus.no_show:
            stat["no_shows"] = int(stat["no_shows"]) + 1
        if int(row["assignment_id"]) in late_cancel_events:
            stat["late_cancellations"] = int(stat["late_cancellations"]) + 1

    worker_rows_out = []
    completion_values = []
    no_show_values = []
    rating_values = []
    for worker_id, stat in worker_stats.items():
        scheduled = int(stat["scheduled_assignments"])
        completed = int(stat["completed_shifts"])
        no_shows = int(stat["no_shows"])
        completion_rate = _safe_rate(completed, scheduled)
        no_show_rate = _safe_rate(no_shows, scheduled)
        ratings_for_worker = worker_ratings.get(worker_id, [])
        avg_rating = (
            round(fmean(ratings_for_worker), 2)
            if ratings_for_worker
            else round(float(workers[worker_id]["rating_avg"] or 0.0), 2)
        )
        worker_rows_out.append(
            {
                "worker_id": worker_id,
                "worker_name": stat["worker_name"],
                "completed_shifts": completed,
                "scheduled_assignments": scheduled,
                "completion_rate": completion_rate,
                "average_rating": avg_rating,
                "no_show_rate": no_show_rate,
                "no_shows": no_shows,
                "late_cancellations": int(stat["late_cancellations"]),
            }
        )
        completion_values.append(completion_rate)
        no_show_values.append(no_show_rate)
        rating_values.append(avg_rating)
    worker_rows_out.sort(key=lambda item: (-item["completion_rate"], -item["average_rating"], item["worker_name"]))

    payroll_by_client: dict[int, dict[str, object]] = {}
    for row in timesheets:
        if not (range_start <= row["starts_at"] <= now):
            continue
        client_org_id = int(row["client_org_id"])
        target = payroll_by_client.setdefault(
            client_org_id,
            {
                "client_org_id": client_org_id,
                "client_name": row["client_name"],
                "hours_worked": 0.0,
                "gross_pay": 0.0,
            },
        )
        target["hours_worked"] = float(target["hours_worked"]) + float(
            row["actual_hours"] or row["scheduled_hours"] or 0.0
        )
        target["gross_pay"] = float(target["gross_pay"]) + float(row["gross_pay"] or 0.0)
    payroll_by_client_list = [
        {
            **item,
            "hours_worked": round(float(item["hours_worked"]), 2),
            "gross_pay": round(float(item["gross_pay"]), 2),
        }
        for item in sorted(payroll_by_client.values(), key=lambda item: item["client_name"])
    ]

    staffed_history = [
        row for row in assignments if row["status"] in STAFFED_ASSIGNMENT_STATUSES and row["starts_at"] >= history_start
    ]
    demand_history_by_bucket: dict[datetime, dict[str, float]] = defaultdict(lambda: {"required_workers": 0, "job_orders": 0})
    demand_history_job_sets: dict[datetime, set[int]] = defaultdict(set)
    for row in shifts:
        if row["starts_at"] < history_start or row["starts_at"] > now:
            continue
        bucket_start = _bucket_floor(row["starts_at"], bucket)
        demand_history_by_bucket[bucket_start]["required_workers"] += int(row["workers_required"] or 0)
        demand_history_job_sets[bucket_start].add(int(row["job_order_id"]))
    history_keys = sorted(demand_history_by_bucket)
    required_series = [float(demand_history_by_bucket[key]["required_workers"]) for key in history_keys]
    jobs_series = [float(len(demand_history_job_sets[key])) for key in history_keys]
    required_slope = _series_slope(required_series)
    jobs_slope = _series_slope(jobs_series)
    required_recent_avg = fmean(required_series[-4:]) if required_series else 0.0
    jobs_recent_avg = fmean(jobs_series[-4:]) if jobs_series else 0.0
    required_by_season: dict[int, list[float]] = defaultdict(list)
    jobs_by_season: dict[int, list[float]] = defaultdict(list)
    for key in history_keys:
        season = _season_key(key, bucket)
        required_by_season[season].append(float(demand_history_by_bucket[key]["required_workers"]))
        jobs_by_season[season].append(float(len(demand_history_job_sets[key])))
    forecast_start = _bucket_next(_bucket_floor(now, bucket), bucket)
    forecast_points = []
    for step in range(1, 7):
        bucket_start = forecast_start
        for _ in range(step - 1):
            bucket_start = _bucket_next(bucket_start, bucket)
        season = _season_key(bucket_start, bucket)
        seasonal_required = fmean(required_by_season[season]) if required_by_season[season] else required_recent_avg
        seasonal_jobs = fmean(jobs_by_season[season]) if jobs_by_season[season] else jobs_recent_avg
        trend_required = (required_series[-1] if required_series else 0.0) + required_slope * step
        trend_jobs = (jobs_series[-1] if jobs_series else 0.0) + jobs_slope * step
        predicted_required = max(0.0, 0.45 * required_recent_avg + 0.35 * trend_required + 0.20 * seasonal_required)
        predicted_jobs = max(0.0, 0.45 * jobs_recent_avg + 0.35 * trend_jobs + 0.20 * seasonal_jobs)
        confidence = max(0.45, min(0.92, 0.88 - (step - 1) * 0.06 + min(len(history_keys), 12) * 0.003))
        band = max(1.0, predicted_required * (1.0 - confidence))
        forecast_points.append(
            {
                "bucket_start": bucket_start.isoformat(),
                "label": _bucket_label(bucket_start, bucket),
                "predicted_required_workers": round(predicted_required, 2),
                "predicted_job_orders": round(predicted_jobs, 2),
                "lower_bound": round(max(0.0, predicted_required - band), 2),
                "upper_bound": round(predicted_required + band, 2),
                "confidence": round(confidence, 2),
            }
        )

    worker_months: dict[int, set[datetime]] = defaultdict(set)
    for row in staffed_history:
        month_bucket = _bucket_floor(row["starts_at"], "month")
        worker_months[int(row["worker_id"])].add(month_bucket)
    cohort_members: dict[datetime, set[int]] = defaultdict(set)
    retention_hits: dict[datetime, dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))
    for worker_id, months in worker_months.items():
        ordered = sorted(months)
        if not ordered:
            continue
        cohort = ordered[0]
        cohort_members[cohort].add(worker_id)
        for month in ordered:
            offset = (month.year - cohort.year) * 12 + (month.month - cohort.month)
            if 0 <= offset <= 5:
                retention_hits[cohort][offset].add(worker_id)
    retention_labels = [f"M{i}" for i in range(6)]
    retention_cohorts = []
    for cohort in sorted(cohort_members):
        members = cohort_members[cohort]
        size = len(members)
        values = []
        for offset in range(6):
            retained = len(retention_hits[cohort][offset])
            values.append(round(retained / size, 4) if size else 0.0)
        retention_cohorts.append(
            {
                "cohort_start": cohort.isoformat(),
                "cohort_label": cohort.strftime("%b %Y"),
                "cohort_size": size,
                "values": values,
            }
        )

    return {
        "scope": {
            "role": scope.role,
            "client_org_ids": scope.org_ids,
            "selected_client_org_id": scope.selected_client_org_id,
            "available_clients": scope.available_clients,
        },
        "filters": {
            "period_days": period_days,
            "bucket": bucket,
            "generated_at": now.isoformat(),
        },
        "summary": {
            "active_workers": len(engaged_active_workers),
            "active_job_orders": len(current_active_job_orders),
            "fill_rate": _safe_rate(total_filled_period, total_slots_period),
            "open_positions": open_positions,
            "upcoming_shifts": len(future_shifts),
        },
        "demand_supply": {"points": demand_supply_points},
        "fill_rate_breakdowns": {
            "by_job_type": [
                {
                    "job_type": job_type,
                    "filled_slots": int(values["filled"]),
                    "total_slots": int(values["slots"]),
                    "fill_rate": _safe_rate(float(values["filled"]), float(values["slots"])),
                }
                for job_type, values in sorted(by_job_type.items(), key=lambda item: item[0].lower())
            ],
            "by_client": [
                {
                    "client_org_id": int(values["client_org_id"]),
                    "client_name": str(values["client_name"]),
                    "filled_slots": int(values["filled"]),
                    "total_slots": int(values["slots"]),
                    "fill_rate": _safe_rate(float(values["filled"]), float(values["slots"])),
                }
                for values in sorted(by_client.values(), key=lambda item: str(item["client_name"]).lower())
            ],
            "by_period": fill_rate_by_period,
        },
        "worker_performance": {
            "summary": {
                "completion_rate": round(fmean(completion_values), 4) if completion_values else 0.0,
                "average_rating": round(fmean(rating_values), 2) if rating_values else 0.0,
                "no_show_rate": round(fmean(no_show_values), 4) if no_show_values else 0.0,
            },
            "workers": worker_rows_out,
        },
        "incident_trends": {"points": incident_points},
        "payroll_summary": {
            "totals": {
                "hours_worked": round(total_hours_period, 2),
                "gross_pay": round(total_pay_period, 2),
            },
            "by_period": payroll_periods,
            "by_client": payroll_by_client_list,
        },
        "forecast": {
            "basis_bucket": bucket,
            "points": forecast_points,
            "assumption": "Forecast blends recent demand, linear trend, and recurring seasonal patterns from historical shifts.",
        },
        "retention_cohorts": {
            "period_labels": retention_labels,
            "cohorts": retention_cohorts,
        },
    }
