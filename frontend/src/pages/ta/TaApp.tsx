import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { api, apiUrl, getToken } from "../../api";
import { fmtShiftDate, formatTimesheetRate } from "../../utils/timesheetFormat";
import { JobOrderForm } from "../../components/jobOrder/JobOrderForm";
import { jobStatusLabelKey } from "../../components/jobOrder/jobOrderStatus";

type JobRow = {
  id: number;
  title: string;
  status: string;
  job_type?: string;
  location_address?: string;
  filled_slots: number;
  total_slots: number;
};

function jobCardStatusStyle(status: string): string {
  switch (status) {
    case "draft":
      return "bg-surface-container-high text-on-surface";
    case "open":
      return "bg-primary-container text-on-primary-container";
    case "partially_filled":
      return "bg-tertiary-container text-on-tertiary-container";
    case "fully_filled":
      return "bg-secondary-container text-on-secondary-container";
    case "completed":
      return "bg-surface-container-highest text-on-surface";
    case "cancelled":
      return "bg-error-container/30 text-on-error-container";
    default:
      return "bg-surface-container-high text-on-surface";
  }
}

function truncate(s: string, n: number) {
  if (s.length <= n) return s;
  return `${s.slice(0, n - 1)}…`;
}

type OrgRow = { id: number; name: string };

export function TaJobsList() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const [rows, setRows] = useState<JobRow[]>([]);
  useEffect(() => {
    api<JobRow[]>("/job-orders").then(setRows);
  }, []);
  return (
    <>
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10 md:mb-12">
        <div>
          <h1 className="font-headline text-4xl md:text-5xl font-extrabold text-on-surface tracking-tighter mb-2">
            {t("job_orders")}
          </h1>
          <p className="text-on-surface-variant font-medium tracking-wide text-sm md:text-base">{t("ta_job_list_subtitle")}</p>
        </div>
        <div className="flex gap-3">
          <button
            type="button"
            className="bg-surface-container-highest text-on-surface px-5 md:px-6 py-3 rounded-xl font-semibold text-sm hover:bg-surface-variant transition-colors flex items-center gap-2 active:scale-95 border border-outline-variant/20"
          >
            <span className="material-symbols-outlined text-[20px]">filter_list</span>
            {t("client_filter")}
          </button>
          <button
            type="button"
            onClick={() => nav("/ta/new")}
            className="glass-cta text-white px-5 md:px-6 py-3 rounded-xl font-bold text-sm shadow-lg flex items-center gap-2 active:scale-95"
          >
            <span className="material-symbols-outlined text-[20px]">add</span>
            {t("job_form_new")}
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {rows.map((j) => (
          <button
            key={j.id}
            type="button"
            onClick={() => nav(`/ta/${j.id}`)}
            className="text-left bg-surface-container-lowest p-6 rounded-3xl group hover:bg-white dark:hover:bg-slate-800 transition-all duration-300 border border-transparent hover:shadow-[0_10px_40px_rgba(43,52,55,0.08)] flex flex-col justify-between min-h-[18rem] relative overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full -mr-16 -mt-16 group-hover:scale-110 transition-transform duration-500 pointer-events-none" />
            <div>
              <div className="flex justify-between items-start mb-6">
                <span
                  className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest ${jobCardStatusStyle(j.status)}`}
                >
                  {t(jobStatusLabelKey(j.status))}
                </span>
                <span className="text-on-surface-variant opacity-40 group-hover:opacity-70">
                  <span className="material-symbols-outlined">arrow_forward</span>
                </span>
              </div>
              <h3 className="font-headline text-xl md:text-2xl font-extrabold text-on-surface leading-tight mb-2 group-hover:text-primary transition-colors">
                {j.title}
              </h3>
              <div className="flex flex-col gap-2 text-on-surface-variant">
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-sm">location_on</span>
                  <span className="text-xs font-medium">
                    {truncate(j.location_address || "—", 42)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-sm">calendar_today</span>
                  <span className="text-xs font-medium">{t("job_card_schedule_detail")}</span>
                </div>
              </div>
            </div>
            <div className="flex items-end justify-between mt-8">
              <div>
                <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">
                  {j.job_type || "—"}
                </p>
                <div className="flex items-center gap-2">
                  <span className="text-2xl font-bold text-primary">{j.filled_slots}</span>
                  <span className="text-lg text-outline-variant font-medium">
                    / {j.total_slots} {t("job_detail_fill_short")}
                  </span>
                </div>
              </div>
              <div className="w-12 h-12 rounded-full bg-surface-container flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-white transition-all duration-300">
                <span className="material-symbols-outlined">arrow_forward</span>
              </div>
            </div>
          </button>
        ))}

        <NavLink
          to="/ta/new"
          className="border-2 border-dashed border-outline-variant/40 p-6 rounded-3xl group hover:border-primary/50 transition-all duration-300 flex flex-col items-center justify-center min-h-[18rem] text-center"
        >
          <div className="w-16 h-16 rounded-full bg-surface-container flex items-center justify-center text-outline-variant group-hover:bg-primary group-hover:text-white transition-all duration-500 mb-4">
            <span className="material-symbols-outlined text-3xl">add_circle</span>
          </div>
          <h3 className="font-headline text-xl font-bold text-on-surface-variant group-hover:text-on-surface transition-colors">
            {t("job_form_new")}
          </h3>
          <p className="text-outline text-sm mt-1">{t("client_create_job_hint")}</p>
        </NavLink>
      </div>
    </>
  );
}

export function TaNewJobPage() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const [orgs, setOrgs] = useState<OrgRow[]>([]);
  useEffect(() => {
    api<OrgRow[]>("/client-organizations").then(setOrgs).catch(() => setOrgs([]));
  }, []);
  return (
    <div>
      <h1 className="font-headline text-3xl md:text-4xl font-extrabold text-on-surface tracking-tight mb-2">{t("job_form_new_ta")}</h1>
      <p className="text-on-surface-variant text-sm mb-8">{t("ta_new_job_intro")}</p>
      <JobOrderForm t={t} mode="ta" organizations={orgs} lightMode onSuccess={() => nav("/ta")} />
    </div>
  );
}

export function TaAnalyticsPage() {
  const { t } = useTranslation();
  const [k, setK] = useState<Record<string, number> | null>(null);
  useEffect(() => {
    api<Record<string, number>>("/analytics/dashboard").then(setK);
  }, []);
  return (
    <div>
      <h1 className="font-headline text-3xl md:text-4xl font-extrabold text-on-surface tracking-tight mb-2">{t("analytics")}</h1>
      <p className="text-on-surface-variant text-sm mb-8">{t("ta_analytics_intro")}</p>
      {k && (
        <pre className="bg-surface-container-lowest border border-outline-variant/25 rounded-2xl p-4 md:p-5 text-xs text-on-surface overflow-auto shadow-sm font-mono">
          {JSON.stringify(k, null, 2)}
        </pre>
      )}
    </div>
  );
}

export function TaExportsPage() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<string | null>(null);

  async function download(path: string, filename: string) {
    setStatus(null);
    const token = getToken();
    const res = await fetch(`/api${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      setStatus(await res.text());
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    setStatus(`Downloaded ${filename}`);
  }

  return (
    <div>
      <h1 className="font-headline text-3xl md:text-4xl font-extrabold text-on-surface tracking-tight mb-2">{t("exports")}</h1>
      <p className="text-on-surface-variant text-sm mb-8">{t("ta_exports_intro")}</p>
      <div className="flex flex-col gap-3 max-w-md">
        <button
          type="button"
          className="rounded-2xl border border-outline-variant/25 bg-surface-container-lowest px-4 py-3 text-left text-sm font-semibold text-primary shadow-sm transition-colors hover:border-primary/40 hover:bg-surface-container-high"
          onClick={() => download("/exports/zoho/job-orders.csv", "zoho_job_orders.csv")}
        >
          job-orders.csv
        </button>
        <button
          type="button"
          className="rounded-2xl border border-outline-variant/25 bg-surface-container-lowest px-4 py-3 text-left text-sm font-semibold text-primary shadow-sm transition-colors hover:border-primary/40 hover:bg-surface-container-high"
          onClick={() => download("/exports/zoho/timesheets.csv", "zoho_timesheets.csv")}
        >
          timesheets.csv
        </button>
        <button
          type="button"
          className="rounded-2xl border border-outline-variant/25 bg-surface-container-lowest px-4 py-3 text-left text-sm font-semibold text-primary shadow-sm transition-colors hover:border-primary/40 hover:bg-surface-container-high"
          onClick={() => download("/exports/zoho/shifts.csv", "zoho_shifts.csv")}
        >
          shifts.csv
        </button>
        <button
          type="button"
          className="rounded-2xl border border-outline-variant/20 bg-secondary-container px-4 py-3 text-left text-sm font-semibold text-on-secondary-container shadow-sm transition-colors hover:brightness-95"
          onClick={() => download("/exports/zoho/job-orders.xlsx", "zoho_job_orders.xlsx")}
        >
          job-orders.xlsx
        </button>
        <button
          type="button"
          className="rounded-2xl border border-outline-variant/20 bg-secondary-container px-4 py-3 text-left text-sm font-semibold text-on-secondary-container shadow-sm transition-colors hover:brightness-95"
          onClick={() => download("/exports/zoho/timesheets.xlsx", "zoho_timesheets.xlsx")}
        >
          timesheets.xlsx
        </button>
      </div>
      {status && <p className="text-sm text-on-surface-variant mt-4">{status}</p>}
    </div>
  );
}

type TaTimesheetRow = {
  id: number;
  job_order_id: number;
  job_title?: string;
  worker_id?: number;
  worker_name?: string;
  shift_id?: number;
  shift_date?: string | null;
  shift_starts_at?: string | null;
  shift_ends_at?: string | null;
  scheduled_hours?: number;
  actual_hours?: number;
  overtime_hours?: number;
  pay_model?: string;
  hourly_rate_snapshot?: number;
  per_shift_rate_snapshot?: number | null;
  gross_pay: number;
  status: string;
  clock_in_at?: string | null;
  clock_out_at?: string | null;
  dispute_flag?: boolean;
  dispute_note?: string | null;
};

function fmtTsShort(iso: string | undefined | null): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function TaTimesheetsPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<TaTimesheetRow[]>([]);
  const [selected, setSelected] = useState<TaTimesheetRow | null>(null);
  const [batchMsg, setBatchMsg] = useState<string | null>(null);
  const [rowExportErr, setRowExportErr] = useState<string | null>(null);

  useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [selected]);

  async function reload() {
    setRows(await api<TaTimesheetRow[]>("/timesheets"));
  }

  useEffect(() => {
    void reload();
  }, []);

  async function verify(id: number) {
    await api(`/timesheets/${id}/ta-verify`, { method: "POST" });
    await reload();
  }

  async function downloadPayrollForEntry(timesheetId: number) {
    setRowExportErr(null);
    const token = getToken();
    const res = await fetch(apiUrl(`/exports/payroll/ta-verified-lines/${timesheetId}.csv`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      setRowExportErr(await res.text());
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ta_payroll_timesheet_${timesheetId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function generateBatchPaymentFile() {
    setBatchMsg(null);
    try {
      const r = await api<{ file: string }>("/payroll/generate-payment-file", { method: "POST" });
      setBatchMsg(r.file);
      await reload();
    } catch (e) {
      setBatchMsg(String(e));
    }
  }

  const sorted = [...rows].sort((a, b) => b.id - a.id);

  return (
    <div>
      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="presentation"
          onClick={() => setSelected(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="ta-timesheet-detail-title"
            className="bg-surface-container-lowest border border-outline-variant/25 rounded-2xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6 text-on-surface"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.key === "Escape" && setSelected(null)}
          >
            <h2 id="ta-timesheet-detail-title" className="font-headline text-lg font-bold mb-4">
              {t("ta_timesheet_detail_title")}
            </h2>
            <p className="text-xs text-on-surface-variant mb-4">
              {t("ta_timesheet_detail_entry_id", { id: selected.id })}
            </p>
            <dl className="grid grid-cols-1 gap-3 text-sm">
              <div>
                <dt className="text-xs font-medium text-on-surface-variant">{t("timesheet_col_worker")}</dt>
                <dd className="font-medium">{selected.worker_name || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-on-surface-variant">{t("timesheet_col_job")}</dt>
                <dd>
                  <span className="font-medium">{selected.job_title || "—"}</span>
                  <span className="text-on-surface-variant"> · #{selected.job_order_id}</span>
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-on-surface-variant">{t("client_timesheet_shift_window")}</dt>
                <dd>
                  {fmtTsShort(selected.shift_starts_at)} → {fmtTsShort(selected.shift_ends_at)}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-on-surface-variant">{t("timesheet_col_scheduled")}</dt>
                <dd>{selected.scheduled_hours != null ? selected.scheduled_hours.toFixed(2) : "—"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-on-surface-variant">{t("timesheet_col_actual")}</dt>
                <dd>{selected.actual_hours != null ? selected.actual_hours.toFixed(2) : "—"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-on-surface-variant">{t("timesheet_col_overtime")}</dt>
                <dd>
                  {selected.overtime_hours != null && selected.overtime_hours > 0
                    ? selected.overtime_hours.toFixed(2)
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-on-surface-variant">{t("timesheet_col_rate")}</dt>
                <dd className="text-on-surface-variant">
                  {selected.pay_model
                    ? formatTimesheetRate({
                        pay_model: selected.pay_model,
                        hourly_rate_snapshot: selected.hourly_rate_snapshot ?? 0,
                        per_shift_rate_snapshot: selected.per_shift_rate_snapshot ?? null,
                      })
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-on-surface-variant">{t("timesheet_col_gross")}</dt>
                <dd className="font-semibold">${selected.gross_pay.toFixed(2)}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-on-surface-variant">{t("timesheet_col_status")}</dt>
                <dd>{selected.status}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-on-surface-variant">{t("timesheet_col_clock_in")}</dt>
                <dd>{fmtTsShort(selected.clock_in_at)}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-on-surface-variant">{t("timesheet_col_clock_out")}</dt>
                <dd>{fmtTsShort(selected.clock_out_at)}</dd>
              </div>
              {(selected.dispute_flag || (selected.dispute_note && selected.dispute_note.trim())) && (
                <div className="rounded-xl border border-error-container/40 bg-error-container/10 p-3">
                  <dt className="text-xs font-medium text-error mb-1">{t("ta_timesheet_detail_dispute")}</dt>
                  <dd className="text-sm">{selected.dispute_note?.trim() || "—"}</dd>
                </div>
              )}
            </dl>
            <div className="mt-6 flex justify-end">
              <button
                type="button"
                className="px-4 py-2 rounded-xl text-sm font-semibold bg-primary text-on-primary"
                onClick={() => setSelected(null)}
              >
                {t("ta_timesheet_detail_close")}
              </button>
            </div>
          </div>
        </div>
      )}
      <h1 className="font-headline text-3xl md:text-4xl font-extrabold text-on-surface tracking-tight mb-2">{t("ta_tab_timesheets")}</h1>
      <p className="text-on-surface-variant text-sm mb-8 max-w-2xl">{t("timesheets_ta_payroll_intro")}</p>
      {rowExportErr && <p className="text-sm text-error mb-3">{rowExportErr}</p>}
      <div className="overflow-x-auto rounded-xl border border-outline-variant/20">
        <table className="w-full min-w-[1000px] text-left text-sm text-on-surface">
          <thead className="bg-surface-container-low text-xs uppercase text-on-surface-variant">
            <tr>
              <th className="px-3 py-2 font-semibold">{t("timesheet_col_worker")}</th>
              <th className="px-3 py-2 font-semibold">{t("timesheet_col_shift_date")}</th>
              <th className="px-3 py-2 font-semibold">{t("timesheet_col_job")}</th>
              <th className="px-3 py-2 font-semibold">{t("timesheet_col_scheduled")}</th>
              <th className="px-3 py-2 font-semibold">{t("timesheet_col_actual")}</th>
              <th className="px-3 py-2 font-semibold">{t("timesheet_col_overtime")}</th>
              <th className="px-3 py-2 font-semibold">{t("timesheet_col_rate")}</th>
              <th className="px-3 py-2 font-semibold">{t("timesheet_col_gross")}</th>
              <th className="px-3 py-2 font-semibold">{t("timesheet_col_status")}</th>
              <th className="px-3 py-2 font-semibold" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((x) => (
              <tr
                key={x.id}
                className="border-t border-outline-variant/10 cursor-pointer hover:bg-surface-container-low/60 transition-colors"
                onClick={() => setSelected(x)}
              >
                <td className="px-3 py-2 font-medium">{x.worker_name || "—"}</td>
                <td className="px-3 py-2 text-on-surface-variant">
                  {fmtShiftDate(x.shift_date || (x.shift_starts_at ? x.shift_starts_at.slice(0, 10) : null))}
                </td>
                <td className="px-3 py-2">
                  <Link
                    to={`/ta/${x.job_order_id}#shifts`}
                    className="font-semibold text-primary hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {x.job_title?.trim() || "—"}
                  </Link>
                  <span className="block text-[11px] text-on-surface-variant mt-0.5">#{x.job_order_id}</span>
                </td>
                <td className="px-3 py-2">{x.scheduled_hours != null ? x.scheduled_hours.toFixed(2) : "—"}</td>
                <td className="px-3 py-2">{x.actual_hours != null ? x.actual_hours.toFixed(2) : "—"}</td>
                <td className="px-3 py-2">
                  {x.overtime_hours != null && x.overtime_hours > 0 ? x.overtime_hours.toFixed(2) : "—"}
                </td>
                <td className="px-3 py-2 text-on-surface-variant">
                  {x.pay_model
                    ? formatTimesheetRate({
                        pay_model: x.pay_model,
                        hourly_rate_snapshot: x.hourly_rate_snapshot ?? 0,
                        per_shift_rate_snapshot: x.per_shift_rate_snapshot ?? null,
                      })
                    : "—"}
                </td>
                <td className="px-3 py-2 font-semibold">${x.gross_pay.toFixed(2)}</td>
                <td className="px-3 py-2 text-on-surface-variant">
                  {x.status}
                  <span className="block text-[10px] text-on-surface-variant/80 mt-0.5">
                    {fmtTsShort(x.clock_in_at)} / {fmtTsShort(x.clock_out_at)}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <div className="flex flex-col gap-1.5 items-start" onClick={(e) => e.stopPropagation()}>
                    {x.status === "employer_endorsed" && (
                      <button type="button" className="text-primary font-semibold hover:underline" onClick={() => void verify(x.id)}>
                        {t("timesheet_ta_verify")}
                      </button>
                    )}
                    {(x.status === "ta_verified" || x.status === "payment_released") && (
                      <button
                        type="button"
                        className="text-primary font-semibold hover:underline text-left"
                        onClick={() => void downloadPayrollForEntry(x.id)}
                      >
                        {t("timesheet_row_export_payroll")}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sorted.length === 0 && <p className="text-on-surface-variant text-sm mt-4">No timesheet rows.</p>}

      <section className="mt-10 pt-8 border-t border-outline-variant/20">
        <h3 className="font-headline text-lg font-bold text-on-surface mb-2">{t("timesheet_batch_payment_title")}</h3>
        <p className="text-sm text-on-surface-variant mb-3 max-w-xl">{t("payroll_generate_hint")}</p>
        <button
          type="button"
          className="glass-cta text-white px-5 py-3 rounded-xl text-sm font-bold shadow-lg"
          onClick={() => void generateBatchPaymentFile()}
        >
          {t("timesheet_batch_payment_button")}
        </button>
        {batchMsg && <p className="text-sm mt-2 text-on-surface">{batchMsg}</p>}
      </section>
    </div>
  );
}

type TaContractRow = {
  id: number;
  client_org_id: number;
  ta_user_id: number;
  status: string;
  requested_by_user_id: number;
  requested_at: string;
  responded_at: string | null;
  message: string | null;
};

export function TaClientsPage() {
  const { t } = useTranslation();
  const [orgs, setOrgs] = useState<OrgRow[]>([]);
  const [incoming, setIncoming] = useState<TaContractRow[]>([]);
  const [allRows, setAllRows] = useState<TaContractRow[]>([]);
  const [enrollName, setEnrollName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function reload() {
    setErr(null);
    try {
      const [o, inc, all] = await Promise.all([
        api<OrgRow[]>("/client-organizations"),
        api<TaContractRow[]>("/ta-contracts/ta/incoming"),
        api<TaContractRow[]>("/ta-contracts/ta/all"),
      ]);
      setOrgs(o);
      setIncoming(inc);
      setAllRows(all);
    } catch (e) {
      setErr(String(e));
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  async function enroll() {
    const name = enrollName.trim();
    if (!name) return;
    setErr(null);
    setMsg(null);
    try {
      await api("/ta-contracts/enroll-client-organization", { method: "POST", json: { name } });
      setEnrollName("");
      setMsg(t("ta_clients_enrolled"));
      await reload();
    } catch (e) {
      setErr(String(e));
    }
  }

  async function accept(id: number) {
    setErr(null);
    try {
      await api(`/ta-contracts/${id}/accept`, { method: "POST" });
      await reload();
    } catch (e) {
      setErr(String(e));
    }
  }

  async function decline(id: number) {
    setErr(null);
    try {
      await api(`/ta-contracts/${id}/decline`, { method: "POST" });
      await reload();
    } catch (e) {
      setErr(String(e));
    }
  }

  async function terminate(id: number) {
    setErr(null);
    try {
      await api(`/ta-contracts/${id}/terminate`, { method: "POST" });
      await reload();
    } catch (e) {
      setErr(String(e));
    }
  }

  const orgName = (id: number) => orgs.find((o) => o.id === id)?.name ?? `Org #${id}`;

  return (
    <div>
      <h1 className="font-headline text-3xl md:text-4xl font-extrabold text-on-surface tracking-tight mb-2">
        {t("ta_clients_title")}
      </h1>
      <p className="text-on-surface-variant text-sm mb-8 max-w-2xl">{t("ta_clients_intro")}</p>
      {err && <p className="text-sm text-error mb-4">{err}</p>}
      {msg && <p className="text-sm text-primary mb-4">{msg}</p>}

      <section className="rounded-2xl border border-outline-variant/25 bg-surface-container-lowest p-5 mb-8">
        <h2 className="font-headline text-lg font-bold text-on-surface mb-3">{t("ta_clients_enroll_heading")}</h2>
        <div className="flex flex-wrap gap-2 items-end max-w-lg">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs font-medium text-on-surface-variant mb-1">{t("ta_clients_org_name")}</label>
            <input
              className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-3 py-2 text-sm"
              value={enrollName}
              onChange={(e) => setEnrollName(e.target.value)}
              placeholder={t("ta_clients_org_name_ph")}
            />
          </div>
          <button
            type="button"
            className="glass-cta text-white px-4 py-2 rounded-xl text-sm font-bold"
            onClick={() => void enroll()}
          >
            {t("ta_clients_enroll_submit")}
          </button>
        </div>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-lg font-bold text-on-surface mb-3">{t("ta_clients_incoming")}</h2>
        {incoming.length === 0 ? (
          <p className="text-sm text-on-surface-variant">{t("ta_clients_incoming_empty")}</p>
        ) : (
          <ul className="space-y-3">
            {incoming.map((c) => (
              <li
                key={c.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-4 py-3 text-sm"
              >
                <span>
                  {orgName(c.client_org_id)} · {t("ta_clients_request_meta", { id: c.id })}
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="text-sm font-semibold text-primary"
                    onClick={() => void accept(c.id)}
                  >
                    {t("ta_clients_accept")}
                  </button>
                  <button
                    type="button"
                    className="text-sm font-semibold text-error"
                    onClick={() => void decline(c.id)}
                  >
                    {t("ta_clients_decline")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="font-headline text-lg font-bold text-on-surface mb-3">{t("ta_clients_all_heading")}</h2>
        <div className="overflow-x-auto rounded-xl border border-outline-variant/20">
          <table className="w-full text-left text-sm text-on-surface min-w-[480px]">
            <thead className="bg-surface-container-low text-xs uppercase text-on-surface-variant">
              <tr>
                <th className="px-3 py-2">{t("ta_clients_col_org")}</th>
                <th className="px-3 py-2">{t("ta_clients_col_status")}</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {allRows.map((c) => (
                <tr key={c.id} className="border-t border-outline-variant/10">
                  <td className="px-3 py-2">{orgName(c.client_org_id)}</td>
                  <td className="px-3 py-2 text-on-surface-variant">{c.status}</td>
                  <td className="px-3 py-2 text-right">
                    {c.status === "active" && (
                      <button
                        type="button"
                        className="text-xs font-semibold text-error underline"
                        onClick={() => void terminate(c.id)}
                      >
                        {t("ta_clients_terminate")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {allRows.length === 0 && <p className="text-sm text-on-surface-variant mt-2">{t("ta_clients_all_empty")}</p>}
      </section>
    </div>
  );
}

type TaStaffProfile = {
  display_name: string | null;
  email: string | null;
  phone: string | null;
  username: string | null;
};

export function TaProfilePage() {
  const { t } = useTranslation();
  const [profile, setProfile] = useState<TaStaffProfile | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setErr(null);
    api<TaStaffProfile>("/ta/me/profile")
      .then((p) => {
        setProfile(p);
        setDisplayName(p.display_name ?? "");
        setEmail(p.email ?? "");
      })
      .catch((e) => setErr(String(e)));
  }, []);

  async function save() {
    setErr(null);
    setMsg(null);
    setSaving(true);
    try {
      const p = await api<TaStaffProfile>("/ta/me/profile", {
        method: "PUT",
        json: { display_name: displayName.trim(), email: email.trim() },
      });
      setProfile(p);
      setDisplayName(p.display_name ?? "");
      setEmail(p.email ?? "");
      setMsg(t("ta_profile_saved"));
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  }

  const inputClass =
    "w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-4 py-3 text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-2 focus:ring-primary";

  return (
    <div className="max-w-lg">
      <h1 className="font-headline text-3xl md:text-4xl font-extrabold text-on-surface tracking-tight mb-2">
        {t("ta_profile_title")}
      </h1>
      <p className="text-on-surface-variant text-sm mb-8">{t("ta_profile_intro")}</p>
      {err && <p className="text-sm text-error mb-4">{err}</p>}
      {msg && <p className="text-sm text-primary mb-4">{msg}</p>}
      {!profile && !err ? (
        <p className="text-sm text-on-surface-variant">{t("job_detail_profile_loading")}</p>
      ) : profile ? (
        <div className="space-y-5 rounded-2xl border border-outline-variant/25 bg-surface-container-lowest p-6">
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1">{t("ta_profile_display_name")}</label>
            <input
              type="text"
              className={inputClass}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={t("ta_profile_display_name_ph")}
              autoComplete="name"
            />
            <p className="mt-1.5 text-xs text-on-surface-variant">{t("ta_profile_display_name_hint")}</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1">{t("ta_profile_username")}</label>
            <p className="text-sm text-on-surface">{profile.username || "—"}</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1">{t("ta_profile_phone")}</label>
            <p className="text-sm text-on-surface">{profile.phone || "—"}</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1">{t("ta_profile_email_label")}</label>
            <input
              type="email"
              className={inputClass}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("ta_profile_email_ph")}
              autoComplete="email"
            />
            <p className="mt-1.5 text-xs text-on-surface-variant">{t("ta_profile_email_hint")}</p>
          </div>
          <button
            type="button"
            disabled={saving}
            className="glass-cta text-white px-5 py-3 rounded-xl text-sm font-bold shadow-lg disabled:opacity-50"
            onClick={() => void save()}
          >
            {saving ? "…" : t("ta_profile_save")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
