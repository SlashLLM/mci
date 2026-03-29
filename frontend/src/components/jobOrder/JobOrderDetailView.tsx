import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { QRCodeSVG } from "qrcode.react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api";
import { JobStatusBadge } from "./jobOrderStatus";

function ShiftAttendanceQrBlock({
  jobId,
  shift,
  portal,
}: {
  jobId: number;
  shift: { id: number; starts_at: string; ends_at: string };
  portal: boolean;
}) {
  const { t } = useTranslation();
  const [data, setData] = useState<{ clock_in_token: string; clock_out_token: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setErr(null);
    setData(null);
    api<{ clock_in_token: string; clock_out_token: string }>(
      `/client/job-orders/${jobId}/shifts/${shift.id}/attendance-qr`,
    )
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, shift.id]);
  const labelIn = portal ? "text-xs font-semibold text-on-surface mb-1" : "text-xs font-semibold text-slate-200 mb-1";
  const hint = portal ? "text-[11px] text-on-surface-variant mt-2" : "text-[11px] text-slate-500 mt-2";
  return (
    <div
      className={
        portal
          ? "mt-3 grid gap-4 sm:grid-cols-2 border-t border-outline-variant/15 pt-3"
          : "mt-3 grid gap-4 sm:grid-cols-2 border-t border-slate-700/50 pt-3"
      }
    >
      {err && <p className="text-sm text-rose-600 dark:text-rose-400 sm:col-span-2">{err}</p>}
      {!err && !data && <p className={`${hint} sm:col-span-2`}>{t("job_detail_qr_loading")}</p>}
      {data && (
        <>
          <div className="flex flex-col items-center">
            <p className={labelIn}>{t("job_detail_qr_clock_in")}</p>
            <div className="rounded-xl bg-white p-2 shadow-sm">
              <QRCodeSVG value={data.clock_in_token} size={132} level="M" />
            </div>
            <p className={hint}>{t("job_detail_qr_worker_hint")}</p>
          </div>
          <div className="flex flex-col items-center">
            <p className={labelIn}>{t("job_detail_qr_clock_out")}</p>
            <div className="rounded-xl bg-white p-2 shadow-sm">
              <QRCodeSVG value={data.clock_out_token} size={132} level="M" />
            </div>
            <p className={hint}>{t("job_detail_qr_worker_hint")}</p>
          </div>
        </>
      )}
    </div>
  );
}

export type JobOrderDetail = {
  id: number;
  client_org_id: number;
  title: string;
  job_type: string;
  status: string;
  location_address: string;
  location_lat: number;
  location_lng: number;
  workers_required_total: number;
  pay_model: string;
  dispatch_mode: string;
  geofence_radius_m: number;
  filled_slots: number;
  total_slots: number;
  hourly_rate: number | null;
  per_shift_rate: number | null;
  required_skills: string[];
  required_certifications: string[];
  uniform_notes: string | null;
  special_instructions: string | null;
  acceptance_window_minutes: number;
  published_at: string | null;
  shifts: { id: number; starts_at: string; ends_at: string; workers_required: number }[];
  accepted_workers: {
    assignment_id: number;
    shift_id: number;
    shift_starts_at: string;
    shift_ends_at: string;
    worker_profile_id: number;
    worker_name: string;
    assignment_status: string;
    match_score: number | null;
  }[];
  declined_workers: {
    offer_id: number;
    shift_id: number;
    shift_starts_at: string;
    shift_ends_at: string;
    worker_profile_id: number;
    worker_name: string;
  }[];
  rejected_workers: {
    assignment_id: number;
    shift_id: number;
    shift_starts_at: string;
    shift_ends_at: string;
    worker_profile_id: number;
    worker_name: string;
    assignment_status: string;
    match_score: number | null;
  }[];
};

type WorkerProfileDetail = {
  id: number;
  full_name: string;
  phone: string;
  email: string | null;
  languages: string[];
  job_type_preferences: string[];
  skills: string[];
  certifications: string[];
  rating_avg: number;
  tier: string;
  status: string;
};

type Variant = "client" | "ta";

export function JobOrderDetailView({ variant, basePath }: { variant: Variant; basePath: string }) {
  const { jobId } = useParams<{ jobId: string }>();
  const { t } = useTranslation();
  const nav = useNavigate();
  const [job, setJob] = useState<JobOrderDetail | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [profileWorkerId, setProfileWorkerId] = useState<number | null>(null);
  const [profileData, setProfileData] = useState<WorkerProfileDetail | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileErr, setProfileErr] = useState<string | null>(null);
  const portal = variant === "client";

  const normalizeJob = useCallback((j: JobOrderDetail): JobOrderDetail => ({
    ...j,
    accepted_workers: j.accepted_workers ?? [],
    declined_workers: j.declined_workers ?? [],
    rejected_workers: j.rejected_workers ?? [],
  }), []);

  const [actionBusy, setActionBusy] = useState<number | null>(null);
  const showEmployerActions = variant === "client" || variant === "ta";

  useEffect(() => {
    if (!profileWorkerId || !jobId) {
      setProfileData(null);
      setProfileErr(null);
      return;
    }
    let cancelled = false;
    setProfileLoading(true);
    setProfileErr(null);
    api<WorkerProfileDetail>(`/job-orders/${jobId}/worker-profiles/${profileWorkerId}`)
      .then((p) => {
        if (!cancelled) setProfileData(p);
      })
      .catch((e) => {
        if (!cancelled) setProfileErr(String(e));
      })
      .finally(() => {
        if (!cancelled) setProfileLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [profileWorkerId, jobId]);

  useEffect(() => {
    if (profileWorkerId === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setProfileWorkerId(null);
        setProfileData(null);
        setProfileErr(null);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [profileWorkerId]);

  const load = useCallback(() => {
    if (!jobId) return;
    setMsg(null);
    api<JobOrderDetail>(`/job-orders/${jobId}`)
      .then((j) => setJob(normalizeJob(j)))
      .catch((e) => setMsg(String(e)));
  }, [jobId, normalizeJob]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setProfileWorkerId(null);
    setProfileData(null);
    setProfileErr(null);
  }, [jobId]);

  async function publish() {
    if (!jobId) return;
    try {
      await api(`/job-orders/${jobId}/publish`, { method: "POST" });
      load();
    } catch (e) {
      setMsg(String(e));
    }
  }

  async function cancel() {
    if (!jobId) return;
    try {
      await api(`/job-orders/${jobId}/cancel`, { method: "POST" });
      load();
    } catch (e) {
      setMsg(String(e));
    }
  }

  async function complete() {
    if (!jobId) return;
    try {
      await api(`/job-orders/${jobId}/complete`, { method: "POST" });
      load();
    } catch (e) {
      setMsg(String(e));
    }
  }

  async function promoteAssignment(assignmentId: number) {
    setActionBusy(assignmentId);
    setMsg(null);
    try {
      await api(`/job-orders/assignments/${assignmentId}/promote-from-waitlist`, { method: "POST" });
      load();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setActionBusy(null);
    }
  }

  async function rejectAssignment(assignmentId: number) {
    setActionBusy(assignmentId);
    setMsg(null);
    try {
      await api(`/job-orders/assignments/${assignmentId}/reject`, { method: "POST" });
      load();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setActionBusy(null);
    }
  }

  async function moveToWaitlist(assignmentId: number) {
    setActionBusy(assignmentId);
    setMsg(null);
    try {
      await api(`/job-orders/assignments/${assignmentId}/move-to-waitlist`, { method: "POST" });
      load();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setActionBusy(null);
    }
  }

  const backErr = portal ? "text-sm text-primary font-semibold mb-3 hover:underline" : "text-sm text-sky-400 mb-3";
  const titleCls = portal ? "font-headline text-3xl font-extrabold text-on-surface" : "text-xl font-semibold";
  const subCls = portal ? "text-sm text-on-surface-variant mt-1" : "text-sm text-slate-400 mt-1";
  const msgErr = portal ? "text-rose-600 text-sm" : "text-rose-400 text-sm";
  const boxCls = portal
    ? "grid gap-2 text-sm sm:grid-cols-2 bg-surface-container-lowest border border-outline-variant/25 rounded-2xl p-4 text-on-surface shadow-sm"
    : "grid gap-2 text-sm sm:grid-cols-2 bg-slate-900 border border-slate-800 rounded-xl p-4";
  const dtCls = portal ? "text-on-surface-variant" : "text-slate-500";
  const shiftTitle = portal ? "text-sm font-semibold text-on-surface mb-2" : "text-sm font-medium text-slate-300 mb-2";
  const shiftLi = portal
    ? "bg-surface-container-lowest border border-outline-variant/20 rounded-xl px-3 py-2 text-sm text-on-surface"
    : "bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm";
  const shiftTime = portal ? "text-on-surface-variant" : "text-slate-400";
  const pub = portal ? "glass-cta text-white px-3 py-2 rounded-xl text-sm font-semibold" : "bg-sky-600 text-slate-950 px-3 py-1.5 rounded-lg text-sm font-medium";
  const canc = portal ? "border border-rose-300 text-rose-700 bg-white px-3 py-2 rounded-xl text-sm font-semibold" : "bg-rose-900 text-rose-100 px-3 py-1.5 rounded-lg text-sm";
  const comp = portal ? "bg-emerald-700 text-white px-3 py-2 rounded-xl text-sm font-semibold" : "bg-emerald-800 text-emerald-50 px-3 py-1.5 rounded-lg text-sm";
  const loadingCls = portal ? "text-on-surface-variant text-sm" : "text-slate-400 text-sm";

  if (msg && !job) {
    return (
      <div>
        <button type="button" onClick={() => nav(basePath)} className={backErr}>
          {t("back")}
        </button>
        <p className={msgErr}>{msg}</p>
      </div>
    );
  }

  if (!job) {
    return <p className={loadingCls}>…</p>;
  }

  const canClientCancel = variant === "client" && (job.status === "draft" || job.status === "open");
  const clientPublish = variant === "client" && job.status === "draft";
  const taPublish = variant === "ta" && job.status === "draft";
  const taCancel = variant === "ta" && job.status !== "cancelled" && job.status !== "completed";
  const taComplete = variant === "ta" && !["draft", "cancelled", "completed"].includes(job.status);

  const rosterName = portal ? "font-semibold text-on-surface" : "font-semibold text-slate-100";
  const rosterMeta = portal ? "text-xs text-on-surface-variant mt-0.5" : "text-xs text-slate-400 mt-0.5";
  const profileLinkBtn = portal
    ? "text-sm font-semibold text-primary hover:underline shrink-0"
    : "text-sm font-semibold text-sky-400 hover:underline shrink-0";
  const emptyRoster = portal ? "text-sm text-on-surface-variant" : "text-sm text-slate-500";
  const detailsSummary = portal
    ? "text-sm font-semibold text-on-surface cursor-pointer list-none [&::-webkit-details-marker]:hidden"
    : "text-sm font-semibold text-slate-200 cursor-pointer list-none [&::-webkit-details-marker]:hidden";

  function assignmentLabel(status: string) {
    if (status === "confirmed") return t("job_detail_assignment_confirmed");
    if (status === "waitlisted") return t("job_detail_assignment_waitlisted");
    if (status === "applied") return t("job_detail_assignment_applied");
    if (status === "rejected") return t("job_detail_assignment_rejected");
    return status;
  }

  function assignmentBadgeClass(st: string) {
    if (st === "confirmed") {
      return portal
        ? "rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200"
        : "rounded-full bg-emerald-900/50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-200";
    }
    if (st === "rejected") {
      return portal
        ? "rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-rose-900 dark:bg-rose-900/40 dark:text-rose-200"
        : "rounded-full bg-rose-900/50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-rose-200";
    }
    return portal
      ? "rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-900 dark:bg-amber-900/40 dark:text-amber-200"
      : "rounded-full bg-amber-900/50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-200";
  }

  const rosterActionBtn = portal
    ? "rounded-lg border border-outline-variant/40 bg-surface-container-high px-2 py-1.5 text-xs font-semibold text-on-surface hover:bg-surface-variant disabled:opacity-50"
    : "rounded-lg border border-slate-600 bg-slate-800 px-2 py-1.5 text-xs font-semibold text-slate-100 hover:bg-slate-700 disabled:opacity-50";
  const rosterDangerBtn = portal
    ? "rounded-lg border border-rose-300/60 bg-white px-2 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50"
    : "rounded-lg border border-rose-800 bg-rose-950/50 px-2 py-1.5 text-xs font-semibold text-rose-200 hover:bg-rose-900/40 disabled:opacity-50";

  function closeProfileModal() {
    setProfileWorkerId(null);
    setProfileData(null);
    setProfileErr(null);
  }

  return (
    <div className="max-w-3xl space-y-4">
      <button
        type="button"
        onClick={() => nav(basePath)}
        className={portal ? "text-sm text-primary font-semibold hover:underline mb-3" : "text-sm text-sky-400 mb-3"}
      >
        ← {t("back")}
      </button>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className={titleCls}>{job.title}</h2>
          <p className={subCls}>
            #{job.id} · {job.job_type}
          </p>
        </div>
        <JobStatusBadge status={job.status} t={t} variant={portal ? "light" : "dark"} />
      </div>
      {msg && <p className={msgErr}>{msg}</p>}

      <div className="flex flex-wrap gap-2">
        {(clientPublish || taPublish) && (
          <button type="button" className={pub} onClick={publish}>
            {t("job_action_publish")}
          </button>
        )}
        {canClientCancel && (
          <button type="button" className={canc} onClick={cancel}>
            {t("job_action_cancel")}
          </button>
        )}
        {taCancel && (
          <button type="button" className={canc} onClick={cancel}>
            {t("job_action_cancel")}
          </button>
        )}
        {taComplete && (
          <button type="button" className={comp} onClick={complete}>
            {t("job_action_complete")}
          </button>
        )}
      </div>

      <dl className={boxCls}>
        <dt className={dtCls}>{t("job_detail_location")}</dt>
        <dd>{job.location_address}</dd>
        <dt className={dtCls}>{t("job_detail_coords")}</dt>
        <dd>
          {job.location_lat}, {job.location_lng}
        </dd>
        <dt className={dtCls}>{t("job_detail_fill")}</dt>
        <dd>
          {job.filled_slots} / {job.total_slots}
        </dd>
        <dt className={dtCls}>{t("job_detail_pay")}</dt>
        <dd>
          {job.pay_model}
          {job.hourly_rate != null && ` · ${t("job_form_hourly_rate")}: ${job.hourly_rate}`}
          {job.per_shift_rate != null && ` · ${t("job_form_per_shift_rate")}: ${job.per_shift_rate}`}
        </dd>
        <dt className={dtCls}>{t("job_form_skills")}</dt>
        <dd>{job.required_skills?.length ? job.required_skills.join(", ") : "—"}</dd>
        <dt className={dtCls}>{t("job_form_certs")}</dt>
        <dd>{job.required_certifications?.length ? job.required_certifications.join(", ") : "—"}</dd>
        {job.uniform_notes && (
          <>
            <dt className={`${dtCls} sm:col-span-2`}>{t("job_form_uniform_equipment")}</dt>
            <dd className="sm:col-span-2 whitespace-pre-wrap">{job.uniform_notes}</dd>
          </>
        )}
        {job.special_instructions && (
          <>
            <dt className={`${dtCls} sm:col-span-2`}>{t("job_form_special_instructions")}</dt>
            <dd className="sm:col-span-2 whitespace-pre-wrap">{job.special_instructions}</dd>
          </>
        )}
      </dl>

      <div>
        <h3 className={shiftTitle}>{t("job_detail_accepted_workers")}</h3>
        {job.accepted_workers.length === 0 ? (
          <p className={emptyRoster}>{t("job_detail_no_accepted_yet")}</p>
        ) : (
          <ul className="space-y-2">
            {job.accepted_workers.map((w) => (
              <li
                key={w.assignment_id}
                className={`${shiftLi} flex flex-wrap items-center justify-between gap-3`}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={rosterName}>{w.worker_name}</span>
                    <span className={assignmentBadgeClass(w.assignment_status)}>{assignmentLabel(w.assignment_status)}</span>
                  </div>
                  <p className={rosterMeta}>
                    {t("job_detail_shift_time")}: {new Date(w.shift_starts_at).toLocaleString()} →{" "}
                    {new Date(w.shift_ends_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  {showEmployerActions && (w.assignment_status === "waitlisted" || w.assignment_status === "applied") && (
                    <button
                      type="button"
                      className={rosterActionBtn}
                      disabled={actionBusy === w.assignment_id}
                      onClick={() => promoteAssignment(w.assignment_id)}
                    >
                      {w.assignment_status === "applied"
                        ? t("job_detail_accept_application")
                        : t("job_detail_promote_waitlist")}
                    </button>
                  )}
                  {showEmployerActions && w.assignment_status === "confirmed" && (
                    <button
                      type="button"
                      className={rosterActionBtn}
                      disabled={actionBusy === w.assignment_id}
                      onClick={() => moveToWaitlist(w.assignment_id)}
                    >
                      {t("job_detail_move_to_waitlist")}
                    </button>
                  )}
                  {showEmployerActions &&
                    (w.assignment_status === "confirmed" ||
                      w.assignment_status === "waitlisted" ||
                      w.assignment_status === "applied") && (
                      <button
                        type="button"
                        className={rosterDangerBtn}
                        disabled={actionBusy === w.assignment_id}
                        onClick={() => rejectAssignment(w.assignment_id)}
                      >
                        {t("job_detail_reject_worker")}
                      </button>
                    )}
                  <button
                    type="button"
                    className={profileLinkBtn}
                    onClick={() => setProfileWorkerId(w.worker_profile_id)}
                  >
                    {t("job_detail_view_profile")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className={shiftTitle}>{t("job_form_shifts")}</h3>
        <ul className="space-y-2">
          {job.shifts.map((s) => (
            <li key={s.id} className={shiftLi}>
              <div>
                <span className={shiftTime}>{new Date(s.starts_at).toLocaleString()}</span>
                {" → "}
                <span className={shiftTime}>{new Date(s.ends_at).toLocaleString()}</span>
                <span className={portal ? "text-on-surface-variant ml-2" : "text-slate-500 ml-2"}>
                  · {s.workers_required} {t("job_form_workers")}
                </span>
              </div>
              {portal && <ShiftAttendanceQrBlock jobId={job.id} shift={s} portal={portal} />}
            </li>
          ))}
        </ul>
      </div>

      {job.declined_workers.length > 0 && (
        <details className={portal ? "rounded-2xl border border-outline-variant/20 bg-surface-container-lowest/80 p-4" : "rounded-xl border border-slate-800 bg-slate-900/50 p-4"}>
          <summary className={detailsSummary}>
            {t("job_detail_declined_workers")} ({job.declined_workers.length})
          </summary>
          <p className={portal ? "mt-2 text-xs text-on-surface-variant" : "mt-2 text-xs text-slate-500"}>
            {t("job_detail_declined_hint")}
          </p>
          <ul className="mt-3 space-y-2">
            {job.declined_workers.map((w) => (
              <li
                key={w.offer_id}
                className={`${shiftLi} flex flex-wrap items-center justify-between gap-3`}
              >
                <div className="min-w-0 flex-1">
                  <span className={rosterName}>{w.worker_name}</span>
                  <p className={rosterMeta}>
                    {t("job_detail_shift_time")}: {new Date(w.shift_starts_at).toLocaleString()} →{" "}
                    {new Date(w.shift_ends_at).toLocaleString()}
                  </p>
                </div>
                <button
                  type="button"
                  className={profileLinkBtn}
                  onClick={() => setProfileWorkerId(w.worker_profile_id)}
                >
                  {t("job_detail_view_profile")}
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}

      {job.rejected_workers.length > 0 && (
        <details
          className={
            portal
              ? "rounded-2xl border border-rose-200/40 bg-surface-container-lowest/80 p-4 dark:border-rose-900/30"
              : "rounded-xl border border-rose-900/40 bg-slate-900/50 p-4"
          }
        >
          <summary className={detailsSummary}>
            {t("job_detail_rejected_workers")} ({job.rejected_workers.length})
          </summary>
          <p className={portal ? "mt-2 text-xs text-on-surface-variant" : "mt-2 text-xs text-slate-500"}>
            {t("job_detail_rejected_hint")}
          </p>
          <ul className="mt-3 space-y-2">
            {job.rejected_workers.map((w) => (
              <li
                key={w.assignment_id}
                className={`${shiftLi} flex flex-wrap items-center justify-between gap-3`}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={rosterName}>{w.worker_name}</span>
                    <span className={assignmentBadgeClass("rejected")}>{assignmentLabel("rejected")}</span>
                  </div>
                  <p className={rosterMeta}>
                    {t("job_detail_shift_time")}: {new Date(w.shift_starts_at).toLocaleString()} →{" "}
                    {new Date(w.shift_ends_at).toLocaleString()}
                  </p>
                </div>
                <button
                  type="button"
                  className={profileLinkBtn}
                  onClick={() => setProfileWorkerId(w.worker_profile_id)}
                >
                  {t("job_detail_view_profile")}
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}

      {profileWorkerId !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="presentation"
          onClick={closeProfileModal}
        >
          <div
            role="dialog"
            aria-labelledby="worker-profile-title"
            className={
              portal
                ? "max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-outline-variant/25 bg-surface-container-lowest p-6 text-on-surface shadow-xl"
                : "max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-slate-700 bg-slate-900 p-6 text-slate-100 shadow-xl"
            }
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between gap-2">
              <h2 id="worker-profile-title" className={portal ? "font-headline text-xl font-extrabold" : "text-lg font-semibold"}>
                {t("job_detail_worker_profile")}
              </h2>
              <button
                type="button"
                onClick={closeProfileModal}
                className={
                  portal
                    ? "rounded-lg px-2 py-1 text-sm font-semibold text-primary hover:bg-surface-container-high"
                    : "rounded-lg px-2 py-1 text-sm font-semibold text-sky-400 hover:bg-slate-800"
                }
              >
                {t("job_detail_close")}
              </button>
            </div>
            {profileLoading && <p className={emptyRoster}>{t("job_detail_profile_loading")}</p>}
            {profileErr && <p className={msgErr}>{profileErr}</p>}
            {profileData && !profileLoading && (
              <dl className={portal ? "grid gap-3 text-sm" : "grid gap-3 text-sm"}>
                <div>
                  <dt className={dtCls}>{t("wizard_name")}</dt>
                  <dd className={portal ? "font-medium" : "font-medium text-slate-100"}>{profileData.full_name || "—"}</dd>
                </div>
                <div>
                  <dt className={dtCls}>{t("job_detail_profile_phone")}</dt>
                  <dd>{profileData.phone || "—"}</dd>
                </div>
                <div>
                  <dt className={dtCls}>{t("job_detail_profile_email")}</dt>
                  <dd>{profileData.email ?? "—"}</dd>
                </div>
                <div>
                  <dt className={dtCls}>{t("job_detail_profile_tier")}</dt>
                  <dd>{profileData.tier}</dd>
                </div>
                <div>
                  <dt className={dtCls}>{t("job_detail_profile_rating")}</dt>
                  <dd>{Number(profileData.rating_avg).toFixed(1)}</dd>
                </div>
                <div>
                  <dt className={dtCls}>{t("job_detail_profile_status")}</dt>
                  <dd>{profileData.status}</dd>
                </div>
                <div>
                  <dt className={dtCls}>{t("job_detail_profile_languages")}</dt>
                  <dd>{profileData.languages?.length ? profileData.languages.join(", ") : "—"}</dd>
                </div>
                <div>
                  <dt className={dtCls}>{t("job_detail_profile_job_types")}</dt>
                  <dd>{profileData.job_type_preferences?.length ? profileData.job_type_preferences.join(", ") : "—"}</dd>
                </div>
                <div>
                  <dt className={dtCls}>{t("job_detail_profile_skills")}</dt>
                  <dd>{profileData.skills?.length ? profileData.skills.join(", ") : "—"}</dd>
                </div>
                <div>
                  <dt className={dtCls}>{t("job_detail_profile_certs")}</dt>
                  <dd>{profileData.certifications?.length ? profileData.certifications.join(", ") : "—"}</dd>
                </div>
              </dl>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
