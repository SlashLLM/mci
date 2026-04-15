from app.models import JobOrder, PayModel


def compute_timesheet_pay(
    job: JobOrder,
    scheduled_hours: float,
    actual_hours: float,
    overtime_hours: float,
) -> tuple[float, float]:
    """Returns (gross_pay, overtime_hours clamped)."""
    hr = float(job.hourly_rate or 0)
    ps = float(job.per_shift_rate or 0)
    mult = float(job.overtime_multiplier or 1.5)

    ot_hours = max(0.0, overtime_hours)
    regular_actual = max(0.0, actual_hours - ot_hours)

    if job.pay_model == PayModel.hourly:
        payable_hours = max(0.0, max(actual_hours, scheduled_hours))
        regular_hourly = max(0.0, payable_hours - ot_hours)
        gross = regular_hourly * hr + ot_hours * hr * mult
        return round(gross, 2), ot_hours

    if job.pay_model == PayModel.per_shift:
        gross = ps if actual_hours > 0 else 0.0
        return round(gross, 2), ot_hours

    # mixed: hourly with per-shift minimum when shift worked
    hourly_part = regular_actual * hr + ot_hours * hr * mult
    gross = max(hourly_part, ps if actual_hours > 0 else 0.0)
    return round(gross, 2), ot_hours
