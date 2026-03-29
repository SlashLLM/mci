import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api, getToken } from "../../api";
import { JobOrderForm } from "../../components/jobOrder/JobOrderForm";
import { JobStatusBadge } from "../../components/jobOrder/jobOrderStatus";

type JobRow = {
  id: number;
  title: string;
  status: string;
  filled_slots: number;
  total_slots: number;
};

type OrgRow = { id: number; name: string };

/** Layout: nav targets are siblings under `/ta` (see App.tsx). */
export function TaLayout() {
  const { t } = useTranslation();
  const link = "px-3 py-2 rounded-lg text-sm data-[active]:bg-slate-800";
  return (
    <div>
      <nav className="flex flex-wrap gap-2 mb-6 border-b border-slate-800 pb-3">
        <NavLink className={link} to="." end relative="route">
          {t("job_orders")}
        </NavLink>
        <NavLink className={link} to="new" relative="route">
          {t("job_form_new")}
        </NavLink>
        <NavLink className={link} to="analytics" relative="route">
          {t("analytics")}
        </NavLink>
        <NavLink className={link} to="exports" relative="route">
          {t("exports")}
        </NavLink>
        <NavLink className={link} to="timesheets" relative="route">
          {t("timesheets")}
        </NavLink>
        <NavLink className={link} to="payroll" relative="route">
          {t("payroll")}
        </NavLink>
      </nav>
      <Outlet />
    </div>
  );
}

export function TaJobsList() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const [rows, setRows] = useState<JobRow[]>([]);
  useEffect(() => {
    api<JobRow[]>("/job-orders").then(setRows);
  }, []);
  return (
    <div>
      <h2 className="text-xl font-semibold mb-3">{t("job_orders")}</h2>
      <ul className="space-y-2">
        {rows.map((j) => (
          <li key={j.id}>
            <button
              type="button"
              className="w-full text-left bg-slate-900 border border-slate-800 rounded-xl p-4 hover:border-slate-600 transition-colors flex flex-wrap justify-between gap-2"
              onClick={() => nav(`/ta/${j.id}`)}
            >
              <div>
                <div className="font-medium">{j.title}</div>
                <div className="flex flex-wrap items-center gap-2 mt-1">
                  <JobStatusBadge status={j.status} t={t} />
                  <span className="text-xs text-slate-500">
                    {j.filled_slots}/{j.total_slots} {t("job_detail_fill_short")}
                  </span>
                </div>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
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
      <h2 className="text-xl font-semibold mb-4">{t("job_form_new_ta")}</h2>
      <JobOrderForm t={t} mode="ta" organizations={orgs} onSuccess={() => nav("/ta")} />
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
      <h2 className="text-xl font-semibold mb-3">{t("analytics")}</h2>
      {k && (
        <pre className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-xs overflow-auto">{JSON.stringify(k, null, 2)}</pre>
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
      <h2 className="text-xl font-semibold mb-3">{t("exports")}</h2>
      <div className="flex flex-col gap-2 max-w-sm">
        <button type="button" className="bg-slate-800 rounded-xl px-4 py-3 text-left text-sky-300" onClick={() => download("/exports/zoho/job-orders.csv", "zoho_job_orders.csv")}>
          job-orders.csv
        </button>
        <button type="button" className="bg-slate-800 rounded-xl px-4 py-3 text-left text-sky-300" onClick={() => download("/exports/zoho/timesheets.csv", "zoho_timesheets.csv")}>
          timesheets.csv
        </button>
        <button type="button" className="bg-slate-800 rounded-xl px-4 py-3 text-left text-sky-300" onClick={() => download("/exports/zoho/shifts.csv", "zoho_shifts.csv")}>
          shifts.csv
        </button>
        <button type="button" className="bg-slate-800 rounded-xl px-4 py-3 text-left text-emerald-300" onClick={() => download("/exports/zoho/job-orders.xlsx", "zoho_job_orders.xlsx")}>
          job-orders.xlsx
        </button>
        <button type="button" className="bg-slate-800 rounded-xl px-4 py-3 text-left text-emerald-300" onClick={() => download("/exports/zoho/timesheets.xlsx", "zoho_timesheets.xlsx")}>
          timesheets.xlsx
        </button>
      </div>
      {status && <p className="text-xs text-slate-400 mt-2">{status}</p>}
    </div>
  );
}

export function TaTimesheetsPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<unknown[]>([]);
  useEffect(() => {
    api<unknown[]>("/timesheets").then(setRows);
  }, []);
  async function verify(id: number) {
    await api(`/timesheets/${id}/ta-verify`, { method: "POST" });
    setRows(await api<unknown[]>("/timesheets"));
  }
  return (
    <div>
      <h2 className="text-xl font-semibold mb-3">{t("timesheets")}</h2>
      <ul className="space-y-2">
        {(rows as { id: number; gross_pay: number; status: string }[]).map((x) => (
          <li key={x.id} className="bg-slate-900 border border-slate-800 rounded-xl p-3 flex justify-between gap-2 text-sm">
            <span>
              #{x.id} · ${x.gross_pay.toFixed(2)} · {x.status}
            </span>
            {x.status === "employer_endorsed" && (
              <button type="button" className="text-sky-400" onClick={() => verify(x.id)}>
                TA verify
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TaPayrollPage() {
  const { t } = useTranslation();
  const [msg, setMsg] = useState<string | null>(null);
  async function gen() {
    try {
      const r = await api<{ file: string }>("/payroll/generate-payment-file", { method: "POST" });
      setMsg(r.file);
    } catch (e) {
      setMsg(String(e));
    }
  }
  return (
    <div>
      <h2 className="text-xl font-semibold mb-3">{t("payroll")}</h2>
      <button type="button" className="bg-sky-600 text-slate-950 px-4 py-2 rounded-xl font-medium" onClick={gen}>
        Generate payment CSV
      </button>
      {msg && <p className="text-sm mt-2 text-slate-300">{msg}</p>}
    </div>
  );
}
