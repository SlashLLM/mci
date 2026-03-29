from datetime import datetime, timezone

from app.services.attendance_rules import (
    clock_in_earliest_utc,
    clock_in_is_late,
    clock_in_time_is_late,
    is_clock_in_too_early,
    is_late_window_without_clock_in,
    is_past_shift_end,
    late_threshold_utc,
)


def _utc(*args, **kwargs):
    return datetime(*args, tzinfo=timezone.utc, **kwargs)


def test_clock_in_earliest_is_ten_minutes_before_start():
    start = _utc(2026, 3, 25, 14, 0, 0)
    assert clock_in_earliest_utc(start) == _utc(2026, 3, 25, 13, 50, 0)


def test_too_early_before_window():
    start = _utc(2026, 3, 25, 14, 0, 0)
    now = _utc(2026, 3, 25, 13, 49, 0)
    assert is_clock_in_too_early(now, start) is True


def test_not_too_early_at_window_open():
    start = _utc(2026, 3, 25, 14, 0, 0)
    now = _utc(2026, 3, 25, 13, 50, 0)
    assert is_clock_in_too_early(now, start) is False


def test_past_shift_end():
    end = _utc(2026, 3, 25, 18, 0, 0)
    assert is_past_shift_end(_utc(2026, 3, 25, 18, 0, 0), end) is True
    assert is_past_shift_end(_utc(2026, 3, 25, 17, 59, 59), end) is False


def test_late_threshold_ten_minutes_after_start():
    start = _utc(2026, 3, 25, 14, 0, 0)
    assert late_threshold_utc(start) == _utc(2026, 3, 25, 14, 10, 0)


def test_clock_in_is_late_after_grace():
    start = _utc(2026, 3, 25, 14, 0, 0)
    assert clock_in_is_late(_utc(2026, 3, 25, 14, 10, 1), start) is True
    assert clock_in_is_late(_utc(2026, 3, 25, 14, 10, 0), start) is False


def test_clock_in_time_is_late():
    start = _utc(2026, 3, 25, 14, 0, 0)
    assert clock_in_time_is_late(_utc(2026, 3, 25, 14, 11, 0), start) is True


def test_late_window_without_clock_in():
    start = _utc(2026, 3, 25, 14, 0, 0)
    now = _utc(2026, 3, 25, 14, 11, 0)
    assert is_late_window_without_clock_in(now, start, has_clock_in=False) is True
    assert is_late_window_without_clock_in(now, start, has_clock_in=True) is False


def test_naive_datetime_treated_as_utc():
    start = datetime(2026, 3, 25, 14, 0, 0)
    earliest = clock_in_earliest_utc(start)
    assert earliest.tzinfo == timezone.utc
    assert earliest == _utc(2026, 3, 25, 13, 50, 0)
