import { useEffect, useState } from "react";
import { api } from "../../api";

type ReportStatus = "open" | "under_review" | "resolved";

type AdminReportRow = {
  id: number;
  status: ReportStatus;
  reason: string;
  created_at: string | null;
  updated_at: string | null;
  shift_assignment_id: number;
  job_order_id: number;
  job_order_name: string;
  shift_id: number;
  shift_starts_at: string | null;
  shift_ends_at: string | null;
  worker_user_id: number;
  worker_name: string | null;
  worker_email: string | null;
  client_org_id: number | null;
  client_org_name: string | null;
  contracted_ta_user_id: number | null;
  contracted_ta_name: string | null;
};

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
  } catch {
    return value;
  }
}

export function AdminReportsPage() {
  const [rows, setRows] = useState<AdminReportRow[]>([]);
  const [statusFilter, setStatusFilter] = useState<"all" | ReportStatus>("all");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function reload() {
    setErr(null);
    const suffix = statusFilter === "all" ? "" : `?status_filter=${statusFilter}`;
    const data = await api<AdminReportRow[]>(`/worker-reports/admin${suffix}`);
    setRows(data);
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function updateStatus(reportId: number, status: ReportStatus) {
    setBusyId(reportId);
    setErr(null);
    try {
      await api(`/worker-reports/admin/${reportId}/status`, { method: "PATCH", json: { status } });
      await reload();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-headline text-3xl md:text-4xl font-extrabold text-on-surface tracking-tight mb-2">Reports</h1>
        <p className="text-on-surface-variant text-sm">Worker-submitted shift reports for admin review.</p>
      </div>
      {err && <p className="text-sm text-error">{err}</p>}
      <div className="flex flex-wrap gap-2">
        <select
          className="rounded-xl border border-outline-variant/30 bg-surface-container-low px-3 py-2 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as "all" | ReportStatus)}
          aria-label="Report status filter"
        >
          <option value="all">All statuses</option>
          <option value="open">Open</option>
          <option value="under_review">Under review</option>
          <option value="resolved">Resolved</option>
        </select>
        <button
          type="button"
          className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary"
          onClick={() => void reload()}
        >
          Refresh
        </button>
      </div>
      <div className="overflow-x-auto rounded-xl border border-outline-variant/20">
        <table className="w-full min-w-[1200px] text-left text-sm text-on-surface">
          <thead className="bg-surface-container-low text-xs uppercase text-on-surface-variant">
            <tr>
              <th className="px-3 py-2">Job order</th>
              <th className="px-3 py-2">Shift time</th>
              <th className="px-3 py-2">Worker</th>
              <th className="px-3 py-2">Client</th>
              <th className="px-3 py-2">Contracted TA</th>
              <th className="px-3 py-2">Reason</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Created</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-outline-variant/10 align-top">
                <td className="px-3 py-2">
                  <p className="font-medium">{row.job_order_name || `#${row.job_order_id}`}</p>
                  <p className="text-xs text-on-surface-variant">Job #{row.job_order_id}</p>
                </td>
                <td className="px-3 py-2">
                  <p>{formatDateTime(row.shift_starts_at)}</p>
                  <p className="text-xs text-on-surface-variant">to {formatDateTime(row.shift_ends_at)}</p>
                </td>
                <td className="px-3 py-2">
                  <p>{row.worker_name || "—"}</p>
                  <p className="text-xs text-on-surface-variant">{row.worker_email || "—"}</p>
                </td>
                <td className="px-3 py-2">{row.client_org_name || "—"}</td>
                <td className="px-3 py-2">{row.contracted_ta_name || "—"}</td>
                <td className="px-3 py-2 max-w-[18rem] whitespace-pre-wrap break-words">{row.reason}</td>
                <td className="px-3 py-2">{row.status}</td>
                <td className="px-3 py-2">{formatDateTime(row.created_at)}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-col gap-1.5 items-start">
                    {row.status !== "open" && (
                      <button
                        type="button"
                        disabled={busyId === row.id}
                        className="text-xs font-semibold text-primary hover:underline disabled:opacity-50"
                        onClick={() => void updateStatus(row.id, "open")}
                      >
                        Mark open
                      </button>
                    )}
                    {row.status !== "under_review" && (
                      <button
                        type="button"
                        disabled={busyId === row.id}
                        className="text-xs font-semibold text-primary hover:underline disabled:opacity-50"
                        onClick={() => void updateStatus(row.id, "under_review")}
                      >
                        Mark under review
                      </button>
                    )}
                    {row.status !== "resolved" && (
                      <button
                        type="button"
                        disabled={busyId === row.id}
                        className="text-xs font-semibold text-emerald-700 hover:underline disabled:opacity-50"
                        onClick={() => void updateStatus(row.id, "resolved")}
                      >
                        Mark resolved
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
