export type TimesheetRateFields = {
  pay_model: string;
  hourly_rate_snapshot: number;
  per_shift_rate_snapshot: number | null;
};

export function formatSgd(value: number): string {
  return `SGD ${Number(value || 0).toFixed(2)}`;
}

export function formatTimesheetRate(x: TimesheetRateFields): string {
  const hr = Number(x.hourly_rate_snapshot) || 0;
  const ps = x.per_shift_rate_snapshot != null ? Number(x.per_shift_rate_snapshot) : null;
  if (x.pay_model === "per_shift" && ps != null && ps > 0) return `${formatSgd(ps)}/shift`;
  if (x.pay_model === "hourly" && hr > 0) return `${formatSgd(hr)}/hr`;
  if (x.pay_model === "mixed") {
    const parts: string[] = [];
    if (hr > 0) parts.push(`${formatSgd(hr)}/hr`);
    if (ps != null && ps > 0) parts.push(`${formatSgd(ps)}/shift min`);
    return parts.length ? parts.join(" · ") : "—";
  }
  if (hr > 0) return `${formatSgd(hr)}/hr`;
  if (ps != null && ps > 0) return `${formatSgd(ps)}/shift`;
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
