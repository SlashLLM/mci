import { Fragment, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../../api";

type AnalyticsBucket = "day" | "week" | "month";

type DashboardResponse = {
  scope: {
    role: string;
    client_org_ids: number[];
    selected_client_org_id: number | null;
    available_clients: Array<{ id: number; name: string }>;
  };
  filters: {
    period_days: number;
    bucket: AnalyticsBucket;
    generated_at: string;
  };
  summary: {
    active_workers: number;
    active_job_orders: number;
    fill_rate: number;
    open_positions: number;
    upcoming_shifts: number;
  };
  demand_supply: {
    points: Array<{
      bucket_start: string;
      label: string;
      job_orders: number;
      required_workers: number;
      filled_workers: number;
      open_positions: number;
      available_workers: number;
      fill_rate: number;
    }>;
  };
  fill_rate_breakdowns: {
    by_job_type: Array<{ job_type: string; filled_slots: number; total_slots: number; fill_rate: number }>;
    by_client: Array<{ client_org_id: number; client_name: string; filled_slots: number; total_slots: number; fill_rate: number }>;
    by_period: Array<{ bucket_start: string; label: string; filled_slots: number; total_slots: number; fill_rate: number }>;
  };
  worker_performance: {
    summary: {
      completion_rate: number;
      average_rating: number;
      no_show_rate: number;
    };
    workers: Array<{
      worker_id: number;
      worker_name: string;
      completed_shifts: number;
      scheduled_assignments: number;
      completion_rate: number;
      average_rating: number;
      no_show_rate: number;
      no_shows: number;
      late_cancellations: number;
    }>;
  };
  incident_trends: {
    points: Array<{
      bucket_start: string;
      label: string;
      scheduled_assignments: number;
      no_shows: number;
      late_cancellations: number;
      no_show_rate: number;
      late_cancellation_rate: number;
    }>;
  };
  payroll_summary: {
    totals: { hours_worked: number; gross_pay: number };
    by_period: Array<{ bucket_start: string; label: string; hours_worked: number; gross_pay: number }>;
    by_client: Array<{ client_org_id: number; client_name: string; hours_worked: number; gross_pay: number }>;
  };
  forecast: {
    basis_bucket: AnalyticsBucket;
    points: Array<{
      bucket_start: string;
      label: string;
      predicted_required_workers: number;
      predicted_job_orders: number;
      lower_bound: number;
      upper_bound: number;
      confidence: number;
    }>;
    assumption: string;
  };
  retention_cohorts: {
    period_labels: string[];
    cohorts: Array<{
      cohort_start: string;
      cohort_label: string;
      cohort_size: number;
      values: number[];
    }>;
  };
};

function Card({
  title,
  value,
  detail,
  icon,
}: {
  title: string;
  value: string;
  detail?: string;
  icon: string;
}) {
  return (
    <div className="rounded-3xl border border-outline-variant/20 bg-surface-container-lowest p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-on-surface-variant">{title}</p>
          <p className="mt-2 font-headline text-3xl font-extrabold tracking-tight text-on-surface">{value}</p>
          {detail && <p className="mt-2 text-sm text-on-surface-variant">{detail}</p>}
        </div>
        <div className="rounded-2xl bg-primary/10 p-3 text-primary">
          <span className="material-symbols-outlined">{icon}</span>
        </div>
      </div>
    </div>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-outline-variant/20 bg-surface-container-lowest p-5 shadow-sm">
      <div className="mb-5">
        <h2 className="font-headline text-xl font-bold text-on-surface">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-on-surface-variant">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

function num(v: number) {
  return new Intl.NumberFormat().format(v);
}

function money(v: number) {
  return `SGD ${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(v)}`;
}

function hourText(v: number) {
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 }).format(v)}h`;
}

function HeatCell({ value }: { value: number }) {
  const alpha = Math.max(0.12, Math.min(1, value));
  return (
    <div
      className="flex h-10 items-center justify-center rounded-xl text-xs font-semibold text-on-surface"
      style={{ backgroundColor: `rgba(61, 121, 212, ${alpha})` }}
    >
      {pct(value)}
    </div>
  );
}

export default function PortalAnalyticsDashboard({
  role,
  title,
  subtitle,
}: {
  role: "client" | "ta" | "admin";
  title: string;
  subtitle: string;
}) {
  const { t } = useTranslation();
  const [periodDays, setPeriodDays] = useState(90);
  const [bucket, setBucket] = useState<AnalyticsBucket>("week");
  const [selectedClientOrgId, setSelectedClientOrgId] = useState<number | null>(null);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.set("period_days", String(periodDays));
        params.set("bucket", bucket);
        if (role !== "client" && selectedClientOrgId != null) {
          params.set("client_org_id", String(selectedClientOrgId));
        }
        const res = await api<DashboardResponse>(`/analytics/portal-dashboard?${params.toString()}`);
        if (cancelled) return;
        setData(res);
      } catch (e) {
        if (cancelled) return;
        setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [bucket, periodDays, role, selectedClientOrgId]);

  const clientOptions = data?.scope.available_clients ?? [];
  const selectedClientName = useMemo(() => {
    if (!data) return null;
    if (role === "client") return clientOptions[0]?.name ?? null;
    if (selectedClientOrgId == null) return t(role === "admin" ? "analytics_scope_all_clients" : "analytics_scope_all_contracted");
    return clientOptions.find((client) => client.id === selectedClientOrgId)?.name ?? null;
  }, [clientOptions, data, role, selectedClientOrgId, t]);

  const workerRows = data?.worker_performance.workers ?? [];
  const topWorkers = workerRows.slice(0, 8);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h1 className="font-headline text-3xl font-extrabold tracking-tight text-on-surface md:text-4xl">{title}</h1>
          <p className="mt-2 max-w-3xl text-sm text-on-surface-variant md:text-base">{subtitle}</p>
          {selectedClientName && <p className="mt-2 text-sm font-medium text-primary">{selectedClientName}</p>}
        </div>
        <div className="grid gap-3 rounded-3xl border border-outline-variant/20 bg-surface-container-lowest p-4 md:grid-cols-3">
          <label className="text-sm">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-on-surface-variant">
              {t("analytics_period")}
            </span>
            <select
              className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-3 py-2 text-sm"
              value={periodDays}
              onChange={(e) => setPeriodDays(Number(e.target.value))}
            >
              <option value={30}>{t("analytics_period_30")}</option>
              <option value={90}>{t("analytics_period_90")}</option>
              <option value={180}>{t("analytics_period_180")}</option>
              <option value={365}>{t("analytics_period_365")}</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-on-surface-variant">
              {t("analytics_granularity")}
            </span>
            <select
              className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-3 py-2 text-sm"
              value={bucket}
              onChange={(e) => setBucket(e.target.value as AnalyticsBucket)}
            >
              <option value="day">{t("analytics_bucket_day")}</option>
              <option value="week">{t("analytics_bucket_week")}</option>
              <option value="month">{t("analytics_bucket_month")}</option>
            </select>
          </label>
          {role !== "client" && (
            <label className="text-sm">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-on-surface-variant">
                {t("analytics_client_filter")}
              </span>
              <select
                className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-3 py-2 text-sm"
                value={selectedClientOrgId ?? ""}
                onChange={(e) => setSelectedClientOrgId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">{t(role === "admin" ? "analytics_scope_all_clients" : "analytics_scope_all_contracted")}</option>
                {clientOptions.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </header>

      {error && <div className="rounded-2xl border border-error/20 bg-error-container/10 p-4 text-sm text-error">{error}</div>}
      {loading && <div className="rounded-2xl border border-outline-variant/20 bg-surface-container-lowest p-4 text-sm text-on-surface-variant">{t("analytics_loading")}</div>}

      {data && !loading && (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
            <Card title={t("analytics_kpi_active_workers")} value={num(data.summary.active_workers)} icon="groups" />
            <Card title={t("analytics_kpi_active_job_orders")} value={num(data.summary.active_job_orders)} icon="assignment" />
            <Card title={t("analytics_kpi_fill_rate")} value={pct(data.summary.fill_rate)} icon="donut_large" />
            <Card title={t("analytics_kpi_open_positions")} value={num(data.summary.open_positions)} icon="person_add" />
            <Card title={t("analytics_kpi_upcoming_shifts")} value={num(data.summary.upcoming_shifts)} icon="event_upcoming" />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.4fr,1fr]">
            <Section title={t("analytics_demand_supply_title")} subtitle={t("analytics_demand_supply_subtitle")}>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={data.demand_supply.points}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={20} />
                    <YAxis yAxisId="left" />
                    <YAxis yAxisId="right" orientation="right" />
                    <Tooltip />
                    <Legend />
                    <Bar yAxisId="left" dataKey="required_workers" fill="#3b82f6" name={t("analytics_required_workers")} radius={[8, 8, 0, 0]} />
                    <Bar yAxisId="left" dataKey="filled_workers" fill="#22c55e" name={t("analytics_filled_workers")} radius={[8, 8, 0, 0]} />
                    <Line yAxisId="right" type="monotone" dataKey="available_workers" stroke="#a855f7" strokeWidth={3} name={t("analytics_available_workers")} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </Section>

            <Section title={t("analytics_fill_breakdown_title")} subtitle={t("analytics_fill_breakdown_subtitle")}>
              <div className="space-y-4">
                {(role === "ta" ? data.fill_rate_breakdowns.by_client : data.fill_rate_breakdowns.by_job_type)
                  .slice(0, 6)
                  .map((row) => (
                    <div key={"client_name" in row ? `${row.client_org_id}` : row.job_type}>
                      <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                        <span className="font-medium text-on-surface">
                          {"client_name" in row ? row.client_name : row.job_type}
                        </span>
                        <span className="text-on-surface-variant">{pct(row.fill_rate)}</span>
                      </div>
                      <div className="h-2 rounded-full bg-surface-container-high">
                        <div className="h-2 rounded-full bg-primary" style={{ width: `${Math.max(4, row.fill_rate * 100)}%` }} />
                      </div>
                    </div>
                  ))}
              </div>
            </Section>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Section title={t("analytics_fill_trend_title")} subtitle={t("analytics_fill_trend_subtitle")}>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.fill_rate_breakdowns.by_period}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={20} />
                    <YAxis tickFormatter={(value) => `${Math.round(value * 100)}%`} />
                    <Tooltip formatter={(value) => pct(Number(value ?? 0))} />
                    <Legend />
                    <Line type="monotone" dataKey="fill_rate" stroke="#0f766e" strokeWidth={3} dot={false} name={t("analytics_kpi_fill_rate")} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Section>

            <Section title={t("analytics_incidents_title")} subtitle={t("analytics_incidents_subtitle")}>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.incident_trends.points}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={20} />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="no_shows" stroke="#ef4444" strokeWidth={3} dot={false} name={t("analytics_no_shows")} />
                    <Line
                      type="monotone"
                      dataKey="late_cancellations"
                      stroke="#f59e0b"
                      strokeWidth={3}
                      dot={false}
                      name={t("analytics_late_cancellations")}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Section>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
            <Section title={t("analytics_worker_performance_title")} subtitle={t("analytics_worker_performance_subtitle")}>
              <div className="mb-5 grid gap-4 md:grid-cols-3">
                <Card title={t("analytics_completion_rate")} value={pct(data.worker_performance.summary.completion_rate)} icon="task_alt" />
                <Card title={t("analytics_average_rating")} value={data.worker_performance.summary.average_rating.toFixed(2)} icon="star" />
                <Card title={t("analytics_no_show_rate")} value={pct(data.worker_performance.summary.no_show_rate)} icon="warning" />
              </div>
              <div className="overflow-x-auto rounded-2xl border border-outline-variant/15">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead className="bg-surface-container-low text-xs uppercase text-on-surface-variant">
                    <tr>
                      <th className="px-3 py-2">{t("timesheet_col_worker")}</th>
                      <th className="px-3 py-2">{t("analytics_completion_rate")}</th>
                      <th className="px-3 py-2">{t("analytics_average_rating")}</th>
                      <th className="px-3 py-2">{t("analytics_no_show_rate")}</th>
                      <th className="px-3 py-2">{t("analytics_late_cancellations")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topWorkers.map((worker) => (
                      <tr key={worker.worker_id} className="border-t border-outline-variant/10">
                        <td className="px-3 py-2 font-medium text-on-surface">{worker.worker_name}</td>
                        <td className="px-3 py-2">{pct(worker.completion_rate)}</td>
                        <td className="px-3 py-2">{worker.average_rating.toFixed(2)}</td>
                        <td className="px-3 py-2">{pct(worker.no_show_rate)}</td>
                        <td className="px-3 py-2">{num(worker.late_cancellations)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>

            <Section title={t("analytics_payroll_title")} subtitle={t("analytics_payroll_subtitle")}>
              <div className="mb-5 grid gap-4 md:grid-cols-2">
                <Card title={t("analytics_total_hours")} value={hourText(data.payroll_summary.totals.hours_worked)} icon="schedule" />
                <Card title={t("analytics_total_pay")} value={money(data.payroll_summary.totals.gross_pay)} icon="payments" />
              </div>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.payroll_summary.by_period}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={20} />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="hours_worked" fill="#2563eb" name={t("analytics_total_hours")} radius={[8, 8, 0, 0]} />
                    <Bar dataKey="gross_pay" fill="#16a34a" name={t("analytics_total_pay")} radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Section>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
            <Section title={t("analytics_forecast_title")} subtitle={data.forecast.assumption}>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.forecast.points}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={20} />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Area type="monotone" dataKey="upper_bound" fill="#bfdbfe" stroke="#bfdbfe" name={t("analytics_forecast_upper")} />
                    <Area type="monotone" dataKey="lower_bound" fill="#dbeafe" stroke="#dbeafe" name={t("analytics_forecast_lower")} />
                    <Line type="monotone" dataKey="predicted_required_workers" stroke="#1d4ed8" strokeWidth={3} name={t("analytics_forecast_demand")} />
                    <Line type="monotone" dataKey="predicted_job_orders" stroke="#7c3aed" strokeWidth={3} name={t("analytics_forecast_job_orders")} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Section>

            <Section title={t("analytics_payroll_client_breakdown")} subtitle={t("analytics_payroll_client_breakdown_subtitle")}>
              <div className="space-y-3">
                {data.payroll_summary.by_client.length === 0 && (
                  <p className="text-sm text-on-surface-variant">{t("analytics_empty")}</p>
                )}
                {data.payroll_summary.by_client.map((row) => (
                  <div key={row.client_org_id} className="rounded-2xl border border-outline-variant/15 bg-surface-container-low p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-on-surface">{row.client_name}</p>
                        <p className="text-sm text-on-surface-variant">{hourText(row.hours_worked)}</p>
                      </div>
                      <p className="font-semibold text-primary">{money(row.gross_pay)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          </div>

          <Section title={t("analytics_retention_title")} subtitle={t("analytics_retention_subtitle")}>
            <div className="overflow-x-auto">
              <div className="min-w-[680px]">
                <div className="grid grid-cols-[220px_repeat(6,minmax(72px,1fr))] gap-2">
                  <div className="px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-on-surface-variant">
                    {t("analytics_cohort")}
                  </div>
                  {data.retention_cohorts.period_labels.map((label) => (
                    <div key={label} className="px-3 py-2 text-center text-xs font-semibold uppercase tracking-[0.16em] text-on-surface-variant">
                      {label}
                    </div>
                  ))}
                  {data.retention_cohorts.cohorts.map((cohort) => (
                    <Fragment key={cohort.cohort_start}>
                      <div key={`${cohort.cohort_start}-label`} className="rounded-2xl bg-surface-container-low px-3 py-3 text-sm">
                        <div className="font-medium text-on-surface">{cohort.cohort_label}</div>
                        <div className="text-xs text-on-surface-variant">
                          {t("analytics_cohort_size", { count: cohort.cohort_size })}
                        </div>
                      </div>
                      {cohort.values.map((value, idx) => (
                        <HeatCell key={`${cohort.cohort_start}-${idx}`} value={value} />
                      ))}
                    </Fragment>
                  ))}
                </div>
              </div>
            </div>
          </Section>
        </>
      )}
    </div>
  );
}
