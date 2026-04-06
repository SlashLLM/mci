"""Seed demo users, client org, job type weights, and a sample job order (draft)."""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.auth.passwords import hash_password
from app.db.session import AsyncSessionLocal
from app.models import (
    ClientOrganization,
    JobOrder,
    JobOrderStatus,
    JobTypeWeight,
    PayModel,
    Shift,
    User,
    UserRole,
    WorkerProfile,
    WorkerStatus,
    WorkerTier,
)

# Demo-only credentials for POST /auth/login.
DEMO_LOGIN_BY_PHONE: dict[str, tuple[str, str]] = {
    "+6590000001": ("worker", "demo_worker"),
    "+6590000005": ("worker_2", "demo_worker_2"),
    "+6590000006": ("worker_3", "demo_worker_3"),
    "+6590000007": ("worker_4", "demo_worker_4"),
    "+6590000008": ("worker_5", "demo_worker_5"),
    "+6590000002": ("ta", "demo_ta"),
    "+6590000009": ("ta_2", "demo_ta_2"),
    "+6590000003": ("client", "demo_client"),
    "+6590000004": ("admin", "demo_admin"),
}


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for jt, p, r, j, c, t in [
            ("_default", 0.3, 0.25, 0.2, 0.15, 0.1),
            ("Warehouse Worker", 0.25, 0.25, 0.15, 0.25, 0.1),
            ("Packing Assistant", 0.25, 0.25, 0.15, 0.25, 0.1),
        ]:
            r0 = await db.execute(select(JobTypeWeight).where(JobTypeWeight.job_type == jt))
            if r0.scalar_one_or_none():
                continue
            db.add(
                JobTypeWeight(
                    job_type=jt,
                    weight_proximity=p,
                    weight_rating=r,
                    weight_job_type=j,
                    weight_completion=c,
                    weight_tier=t,
                )
            )

        r = await db.execute(select(ClientOrganization).where(ClientOrganization.name == "Demo Warehouse Pte Ltd"))
        org = r.scalar_one_or_none()
        if not org:
            org = ClientOrganization(name="Demo Warehouse Pte Ltd")
            db.add(org)
            await db.flush()

        async def ensure_user(
            phone: str,
            role: UserRole,
            name: str,
            org_id=None,
            *,
            skills: list[str] | None = None,
            certifications: list[str] | None = None,
            location_lat: float = 1.3521,
            location_lng: float = 103.8198,
            rating_avg: float = 4.2,
            tier: WorkerTier = WorkerTier.standard,
        ):
            r2 = await db.execute(select(User).where(User.phone == phone))
            u = r2.scalar_one_or_none()
            if u:
                return u
            u = User(phone=phone, role=role, locale="en", client_org_id=org_id)
            db.add(u)
            await db.flush()
            if role == UserRole.worker:
                db.add(
                    WorkerProfile(
                        user_id=u.id,
                        full_name=name,
                        languages=["en", "zh"],
                        job_type_preferences=["Warehouse Worker", "Packing Assistant"],
                        skills=skills or ["packing"],
                        certifications=certifications or [],
                        availability={"always": True},
                        location_lat=location_lat,
                        location_lng=location_lng,
                        rating_avg=rating_avg,
                        tier=tier,
                        status=WorkerStatus.active,
                        profile_completeness_pct=80,
                    )
                )
            return u

        def apply_demo_login(u: User, phone: str) -> None:
            pair = DEMO_LOGIN_BY_PHONE.get(phone)
            if not pair:
                return
            uname, plain = pair
            u.username = uname
            u.hashed_password = hash_password(plain)

        u_worker = await ensure_user("+6590000001", UserRole.worker, "Lucy Tan")
        apply_demo_login(u_worker, "+6590000001")
        w2 = await ensure_user(
            "+6590000005",
            UserRole.worker,
            "Amir Rahman",
            skills=["packing", "inventory"],
            certifications=["forklift"],
            location_lat=1.3300,
            location_lng=103.8500,
            rating_avg=4.8,
            tier=WorkerTier.preferred,
        )
        apply_demo_login(w2, "+6590000005")
        w3 = await ensure_user(
            "+6590000006",
            UserRole.worker,
            "Mei Lin",
            skills=["cash_handling", "customer_service"],
            certifications=["food_hygiene", "first_aid"],
            location_lat=1.2950,
            location_lng=103.8600,
            rating_avg=4.6,
            tier=WorkerTier.elite,
        )
        apply_demo_login(w3, "+6590000006")
        w4 = await ensure_user(
            "+6590000007",
            UserRole.worker,
            "David Koh",
            skills=["loading", "sorting"],
            certifications=[],
            location_lat=1.3800,
            location_lng=103.7600,
            rating_avg=4.0,
            tier=WorkerTier.standard,
        )
        apply_demo_login(w4, "+6590000007")
        w5 = await ensure_user(
            "+6590000008",
            UserRole.worker,
            "Nur Aisyah",
            skills=["packing", "qc"],
            certifications=["forklift", "wsq_safety"],
            location_lat=1.3150,
            location_lng=103.7000,
            rating_avg=4.9,
            tier=WorkerTier.elite,
        )
        apply_demo_login(w5, "+6590000008")
        u_ta = await ensure_user("+6590000002", UserRole.ta, "Jared TA", None)
        u_ta.display_name = "Jared TA"
        apply_demo_login(u_ta, "+6590000002")
        u_ta_2 = await ensure_user("+6590000009", UserRole.ta, "Samira TA", None)
        u_ta_2.display_name = "Samira TA"
        apply_demo_login(u_ta_2, "+6590000009")
        client_u = await ensure_user("+6590000003", UserRole.client, "Mr Wong", org.id)
        client_u.client_org_id = org.id
        apply_demo_login(client_u, "+6590000003")
        u_admin = await ensure_user("+6590000004", UserRole.admin, "Admin User", None)
        apply_demo_login(u_admin, "+6590000004")

        rj = await db.execute(select(JobOrder).where(JobOrder.title == "Demo packing shift"))
        if not rj.scalar_one_or_none():
            ta = await db.execute(select(User).where(User.phone == "+6590000002"))
            ta_user = ta.scalar_one()
            start = datetime.now(timezone.utc) + timedelta(days=1)
            end = start + timedelta(hours=8)
            job = JobOrder(
                client_org_id=org.id,
                created_by_user_id=ta_user.id,
                title="Demo packing shift",
                job_type="Warehouse Worker",
                location_address="1 Harbourfront Walk, Singapore",
                location_lat=1.2644,
                location_lng=103.8223,
                workers_required_total=3,
                hourly_rate=15.0,
                per_shift_rate=None,
                pay_model=PayModel.hourly,
                required_skills=["packing"],
                required_certifications=[],
                geofence_radius_m=300,
                status=JobOrderStatus.draft,
            )
            db.add(job)
            await db.flush()
            db.add(
                Shift(
                    job_order_id=job.id,
                    starts_at=start,
                    ends_at=end,
                    workers_required=3,
                )
            )
        await db.commit()
        print(
            "Seed complete. Login (POST /auth/login): "
            "worker/demo_worker, worker_2/demo_worker_2, worker_3/demo_worker_3, "
            "worker_4/demo_worker_4, worker_5/demo_worker_5, ta/demo_ta, ta_2/demo_ta_2, "
            "client/demo_client, admin/demo_admin. "
            "OTP still works for these phones when OTP_DEV_MODE is on."
        )


if __name__ == "__main__":
    asyncio.run(main())
