export type TimesheetRateFields = {
  pay_model: string;
  hourly_rate_snapshot: number;
  per_shift_rate_snapshot: number | null;
};

export function formatTimesheetRate(x: TimesheetRateFields): string {
  const hr = Number(x.hourly_rate_snapshot) || 0;
  const ps = x.per_shift_rate_snapshot != null ? Number(x.per_shift_rate_snapshot) : null;
  if (x.pay_model === "per_shift" && ps != null && ps > 0) return `$${ps.toFixed(2)}/shift`;
  if (x.pay_model === "hourly" && hr > 0) return `$${hr.toFixed(2)}/hr`;
  if (x.pay_model === "mixed") {
    const parts: string[] = [];
    if (hr > 0) parts.push(`$${hr.toFixed(2)}/hr`);
    if (ps != null && ps > 0) parts.push(`$${ps.toFixed(2)}/shift min`);
    return parts.length ? parts.join(" · ") : "—";
  }
  if (hr > 0) return `$${hr.toFixed(2)}/hr`;
  if (ps != null && ps > 0) return `$${ps.toFixed(2)}/shift`;
  return "—";
}

export function fmtShiftDate(isoDate: string | undefined | null): string {
  if (!isoDate) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(isoDate + "T12:00:00"));
  } catch {
    return isoDate;
  }
}
