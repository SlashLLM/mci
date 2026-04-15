from app.models import JobOrder, PayModel
from app.services.payroll_calc import compute_timesheet_pay


def test_hourly_pay():
    job = JobOrder(
        pay_model=PayModel.hourly,
        hourly_rate=10.0,
        per_shift_rate=None,
        overtime_multiplier=1.5,
    )
    gross, _ = compute_timesheet_pay(job, 8.0, 10.0, 2.0)
    assert gross == round(8 * 10 + 2 * 10 * 1.5, 2)


def test_hourly_short_shift_still_pays_full_scheduled():
    job = JobOrder(
        pay_model=PayModel.hourly,
        hourly_rate=10.0,
        per_shift_rate=None,
        overtime_multiplier=1.5,
    )
    gross, _ = compute_timesheet_pay(job, 8.0, 6.0, 0.0)
    assert gross == 80.0


def test_hourly_exact_scheduled_pay_unchanged():
    job = JobOrder(
        pay_model=PayModel.hourly,
        hourly_rate=10.0,
        per_shift_rate=None,
        overtime_multiplier=1.5,
    )
    gross, _ = compute_timesheet_pay(job, 8.0, 8.0, 0.0)
    assert gross == 80.0


def test_per_shift():
    job = JobOrder(pay_model=PayModel.per_shift, hourly_rate=0, per_shift_rate=100.0, overtime_multiplier=1.5)
    gross, _ = compute_timesheet_pay(job, 8.0, 8.0, 0.0)
    assert gross == 100.0


def test_geofence():
    from app.services.geo import haversine_m, within_radius

    d = haversine_m(1.2644, 103.8223, 1.2644, 103.8223)
    assert d < 1
    assert within_radius(1.2644, 103.8223, 1.2644, 103.8223, 200)


def test_zoho_job_orders_csv_sync():
    import asyncio

    from app.models import JobOrder, JobOrderStatus, PayModel
    from app.services.zoho_export import export_job_orders_csv

    async def run():
        class Dummy:
            async def get(self, model, id):
                return None

        jobs = [
            JobOrder(
                id=1,
                client_org_id=1,
                created_by_user_id=1,
                title="T",
                job_type="Warehouse Worker",
                location_address="A",
                location_lat=1.0,
                location_lng=103.0,
                workers_required_total=2,
                pay_model=PayModel.hourly,
                hourly_rate=12.0,
                per_shift_rate=None,
                status=JobOrderStatus.open,
            )
        ]

        csv_text = await export_job_orders_csv(Dummy(), jobs)
        assert "Deal_Name" in csv_text
        assert "T" in csv_text

    asyncio.run(run())
