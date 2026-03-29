import type { TFunction } from "i18next";

const BADGE: Record<string, string> = {
  draft: "bg-slate-600 text-slate-100",
  open: "bg-sky-700 text-sky-50",
  partially_filled: "bg-amber-700 text-amber-50",
  fully_filled: "bg-emerald-700 text-emerald-50",
  completed: "bg-slate-500 text-slate-50",
  cancelled: "bg-rose-900 text-rose-100",
};

const BADGE_LIGHT: Record<string, string> = {
  draft: "bg-surface-container-high text-on-surface",
  open: "bg-primary-container text-on-primary-container",
  partially_filled: "bg-tertiary-container text-on-tertiary-container",
  fully_filled: "bg-secondary-container text-on-secondary-container",
  completed: "bg-surface-container-highest text-on-surface",
  cancelled: "bg-error-container/40 text-on-error-container",
};

export function jobStatusLabelKey(status: string): string {
  const map: Record<string, string> = {
    draft: "job_status_draft",
    open: "job_status_open",
    partially_filled: "job_status_partially_filled",
    fully_filled: "job_status_fully_filled",
    completed: "job_status_completed",
    cancelled: "job_status_cancelled",
  };
  return map[status] ?? status;
}

export function JobStatusBadge({
  status,
  t,
  variant = "dark",
}: {
  status: string;
  t: TFunction;
  variant?: "dark" | "light";
}) {
  const map = variant === "light" ? BADGE_LIGHT : BADGE;
  const cls = map[status] ?? (variant === "light" ? "bg-surface-container-high text-on-surface" : "bg-slate-700 text-slate-200");
  return (
    <span className={`inline-block rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-wider ${cls}`}>
      {t(jobStatusLabelKey(status))}
    </span>
  );
}
