"""Shared clock-in window and late thresholds (UTC)."""

from datetime import datetime, timedelta, timezone

CLOCK_IN_OPEN_MINUTES_BEFORE_START = 10
LATE_MINUTES_AFTER_START = 10


def clock_in_earliest_utc(shift_starts_at: datetime) -> datetime:
    start = shift_starts_at if shift_starts_at.tzinfo else shift_starts_at.replace(tzinfo=timezone.utc)
    return start - timedelta(minutes=CLOCK_IN_OPEN_MINUTES_BEFORE_START)


def late_threshold_utc(shift_starts_at: datetime) -> datetime:
    start = shift_starts_at if shift_starts_at.tzinfo else shift_starts_at.replace(tzinfo=timezone.utc)
    return start + timedelta(minutes=LATE_MINUTES_AFTER_START)


def is_clock_in_too_early(now: datetime, shift_starts_at: datetime) -> bool:
    return now < clock_in_earliest_utc(shift_starts_at)


def is_past_shift_end(now: datetime, shift_ends_at: datetime) -> bool:
    end = shift_ends_at if shift_ends_at.tzinfo else shift_ends_at.replace(tzinfo=timezone.utc)
    return now >= end


def is_past_clock_in_grace_deadline(now: datetime, shift_starts_at: datetime) -> bool:
    return now > late_threshold_utc(shift_starts_at)


def is_grace_period_late_punch(clock_in_time: datetime, shift_starts_at: datetime) -> bool:
    t = clock_in_time if clock_in_time.tzinfo else clock_in_time.replace(tzinfo=timezone.utc)
    start = shift_starts_at if shift_starts_at.tzinfo else shift_starts_at.replace(tzinfo=timezone.utc)
    return start < t <= late_threshold_utc(shift_starts_at)


def clock_in_is_late(now: datetime, shift_starts_at: datetime) -> bool:
    return is_past_clock_in_grace_deadline(now, shift_starts_at)


def clock_in_time_is_late(clock_in_time: datetime, shift_starts_at: datetime) -> bool:
    return is_past_clock_in_grace_deadline(clock_in_time, shift_starts_at)


def is_late_window_without_clock_in(now: datetime, shift_starts_at: datetime, has_clock_in: bool) -> bool:
    if has_clock_in:
        return False
    return now > late_threshold_utc(shift_starts_at)
