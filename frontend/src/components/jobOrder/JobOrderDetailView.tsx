import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { QRCodeSVG } from "qrcode.react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api";
import { CertificationMultiPicker } from "../certifications/CertificationMultiPicker";
import { SkillMultiPicker } from "../skills/SkillMultiPicker";
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
    applied_at: string | null;
    rating_avg: number;
    certifications_count: number;
    worker_skills: string[];
    worker_certifications: string[];
    location_lat: number | null;
    location_lng: number | null;
    is_preferred: boolean;
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
  has_ta_payroll?: boolean;
  viewer_can_vet_assignments?: boolean;
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
  const location = useLocation();
  const nav = useNavigate();
  const [job, setJob] = useState<JobOrderDetail | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [profileWorkerId, setProfileWorkerId] = useState<number | null>(null);
  const [profileData, setProfileData] = useState<WorkerProfileDetail | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileErr, setProfileErr] = useState<string | null>(null);
  const [workerTab, setWorkerTab] = useState<"accepted" | "applied">("accepted");
  const [minRating, setMinRating] = useState("");
  const [preferredFirst, setPreferredFirst] = useState(false);
  const [appliedSince, setAppliedSince] = useState("");
  const [minCerts, setMinCerts] = useState("");
  const [maxDistanceKm, setMaxDistanceKm] = useState("");
  const [skillFilters, setSkillFilters] = useState<string[]>([]);
  const [certFilters, setCertFilters] = useState<string[]>([]);
  const [appliedSort, setAppliedSort] = useState<"newest" | "oldest">("newest");
  /** Light “portal” UI (client + TA). Attendance QR API is client-only; see shift list below. */
  const portal = variant === "client" || variant === "ta";

  const normalizeJob = useCallback((j: JobOrderDetail): JobOrderDetail => ({
    ...j,
    accepted_workers: (j.accepted_workers ?? []).map((w) => ({
      ...w,
      worker_skills: w.worker_skills ?? [],
      worker_certifications: w.worker_certifications ?? [],
    })),
    declined_workers: j.declined_workers ?? [],
    rejected_workers: j.rejected_workers ?? [],
    has_ta_payroll: j.has_ta_payroll ?? false,
    viewer_can_vet_assignments: j.viewer_can_vet_assignments ?? true,
  }), []);

  const [actionBusy, setActionBusy] = useState<number | null>(null);
  const showEmployerActions =
    (variant === "client" || variant === "ta") && (job?.viewer_can_vet_assignments ?? true);

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
    if (!job) return;
    if (location.hash !== "#shifts") return;
    const el = document.getElementById("job-detail-shifts");
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [job, location.hash]);

  useEffect(() => {
    setProfileWorkerId(null);
    setProfileData(null);
    setProfileErr(null);
  }, [jobId]);

  const requiredSkillSet = useMemo(() => new Set(job?.required_skills ?? []), [job?.required_skills]);
  const requiredCertSet = useMemo(() => new Set(job?.required_certifications ?? []), [job?.required_certifications]);

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

  const msgErr = "text-rose-600 text-sm";

  if (msg && !job) {
    return (
      <div>
        <button type="button" onClick={() => nav(basePath)} className="text-sm text-primary font-semibold mb-3 hover:underline">
          {t("back")}
        </button>
        <p className={msgErr}>{msg}</p>
      </div>
    );
  }

  if (!job) {
    return <p className="text-on-surface-variant text-sm">…</p>;
  }

  const canClientCancel = variant === "client" && (job.status === "draft" || job.status === "open");
  const clientPublish = variant === "client" && job.status === "draft";
  const taPublish = variant === "ta" && job.status === "draft";
  const taCancel = variant === "ta" && job.status !== "cancelled" && job.status !== "completed";
  const taComplete = variant === "ta" && !["draft", "cancelled", "completed"].includes(job.status);

  const rosterName = "font-semibold text-on-surface";
  const rosterMeta = "text-xs text-on-surface-variant mt-0.5";
  const profileLinkBtn = "text-sm font-semibold text-primary hover:underline shrink-0";
  const emptyRoster = "text-sm text-on-surface-variant";
  const detailsSummary = "text-sm font-semibold text-on-surface cursor-pointer list-none [&::-webkit-details-marker]:hidden";

  function assignmentLabel(status: string) {
    if (status === "confirmed") return t("job_detail_assignment_confirmed");
    if (status === "waitlisted") return t("job_detail_assignment_waitlisted");
    if (status === "applied") return t("job_detail_assignment_applied");
    if (status === "rejected") return t("job_detail_assignment_rejected");
    return status;
  }

  function assignmentBadgeClass(st: string) {
    if (st === "confirmed") {
      return "rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200";
    }
    if (st === "rejected") {
      return "rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-rose-900 dark:bg-rose-900/40 dark:text-rose-200";
    }
    return "rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-900 dark:bg-amber-900/40 dark:text-amber-200";
  }

  function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number) {
    const toRad = (deg: number) => (deg * Math.PI) / 180;
    const dLat = toRad(lat2 - lat1);
    const dLng = toRad(lng2 - lng1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return 6371 * c;
  }

  const rosterActionBtn =
    "rounded-md border border-outline-variant/40 bg-transparent px-2 py-1 text-xs font-medium text-on-surface hover:bg-surface-container disabled:opacity-50";
  const rosterDangerBtn =
    "rounded-md border border-rose-300/60 bg-transparent px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50";

  const acceptedWorkers = job.accepted_workers.filter((w) => w.assignment_status === "confirmed");
  const appliedWorkers = job.accepted_workers.filter((w) => w.assignment_status !== "confirmed");
  const filteredAppliedWorkers = appliedWorkers
    .filter((w) => {
      const ratingPass = minRating ? (w.rating_avg || 0) >= Number(minRating) : true;
      const datePass = appliedSince
        ? !!w.applied_at && new Date(w.applied_at) >= new Date(`${appliedSince}T00:00:00`)
        : true;
      const certPass = minCerts ? (w.certifications_count || 0) >= Number(minCerts) : true;
      const skillPass =
        skillFilters.length > 0
          ? skillFilters.every((skill) => (w.worker_skills || []).includes(skill))
          : true;
      const certFilterPass =
        certFilters.length > 0
          ? certFilters.every((c) => (w.worker_certifications || []).includes(c))
          : true;
      const distancePass = (() => {
        if (!maxDistanceKm) return true;
        if (w.location_lat == null || w.location_lng == null) return false;
        return haversineKm(job.location_lat, job.location_lng, w.location_lat, w.location_lng) <= Number(maxDistanceKm);
      })();
      return ratingPass && datePass && certPass && skillPass && certFilterPass && distancePass;
    })
    .sort((a, b) => {
      if (preferredFirst) {
        const pref = Number(!!b.is_preferred) - Number(!!a.is_preferred);
        if (pref !== 0) return pref;
      }
      const ad = a.applied_at ? new Date(a.applied_at).getTime() : 0;
      const bd = b.applied_at ? new Date(b.applied_at).getTime() : 0;
      return appliedSort === "newest" ? bd - ad : ad - bd;
    });

  function closeProfileModal() {
    setProfileWorkerId(null);
    setProfileData(null);
    setProfileErr(null);
  }

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={() => nav(basePath)}
        className="text-sm text-primary font-semibold hover:underline"
      >
        ← {t("back")}
      </button>
      <section className="rounded-2xl border border-outline-variant/20 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-primary-container px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-on-primary-container">
                #{job.id}
              </span>
              <JobStatusBadge status={job.status} t={t} variant="light" />
            </div>
            <h2 className="font-headline text-4xl font-extrabold text-on-surface">{job.title}</h2>
            <p className="text-on-surface-variant">{job.job_type}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {(clientPublish || taPublish) && (
              <button type="button" className="glass-cta text-white px-3 py-2 rounded-xl text-sm font-semibold" onClick={publish}>
                {t("job_action_publish")}
              </button>
            )}
            {(canClientCancel || taCancel) && (
              <button type="button" className="border border-rose-300 text-rose-700 bg-white px-3 py-2 rounded-xl text-sm font-semibold" onClick={cancel}>
                {t("job_action_cancel")}
              </button>
            )}
            {taComplete && (
              <button type="button" className="bg-emerald-700 text-white px-3 py-2 rounded-xl text-sm font-semibold" onClick={complete}>
                {t("job_action_complete")}
              </button>
            )}
          </div>
        </div>
      </section>
      {msg && <p className={msgErr}>{msg}</p>}

      <div className="grid grid-cols-12 gap-6">
        <section className="col-span-12 lg:col-span-4 space-y-6">
          <div className="rounded-2xl border border-outline-variant/20 p-6">
            <h3 className="mb-4 text-xs font-black uppercase tracking-[0.2em] text-on-surface-variant">{t("job_detail_location")}</h3>
            <div className="space-y-4 text-sm">
              <div>
                <p className="text-xs uppercase text-on-surface-variant">{t("job_detail_location")}</p>
                <p className="font-semibold">{job.location_address}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-on-surface-variant">{t("job_detail_coords")}</p>
                <p className="font-mono text-primary">
                  {job.location_lat}, {job.location_lng}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-outline-variant/20 p-3">
                  <p className="text-xs text-on-surface-variant">{t("job_detail_fill")}</p>
                  <p className="text-xl font-extrabold">
                    {job.filled_slots} / {job.total_slots}
                  </p>
                </div>
                <div className="rounded-xl border border-outline-variant/20 p-3">
                  <p className="text-xs text-on-surface-variant">{t("job_detail_pay")}</p>
                  <p className="text-xl font-extrabold text-primary">
                    {job.hourly_rate != null ? `$${job.hourly_rate}` : job.per_shift_rate != null ? `$${job.per_shift_rate}` : "—"}
                  </p>
                </div>
              </div>
              <div>
                <p className="text-xs uppercase text-on-surface-variant">{t("job_form_skills")}</p>
                <p>{job.required_skills?.length ? job.required_skills.join(", ") : "—"}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-on-surface-variant">{t("job_form_certs")}</p>
                <p>{job.required_certifications?.length ? job.required_certifications.join(", ") : "—"}</p>
              </div>
            </div>
          </div>

          <div id="job-detail-shifts" className="scroll-mt-24 rounded-2xl border border-outline-variant/20 p-6">
            <h3 className="mb-4 text-xs font-black uppercase tracking-[0.2em] text-on-surface-variant">{t("job_form_shifts")}</h3>
            <div className="space-y-4">
              {job.shifts.map((s) => (
                <div key={s.id} className="rounded-xl bg-tertiary-container p-4">
                  <p className="font-semibold text-on-tertiary-container">{new Date(s.starts_at).toLocaleDateString()}</p>
                  <p className="text-sm text-on-tertiary-container">
                    {new Date(s.starts_at).toLocaleString()} → {new Date(s.ends_at).toLocaleString()}
                  </p>
                  <p className="text-xs text-on-tertiary-container mt-1">· {s.workers_required} {t("job_form_workers")}</p>
                  <ShiftAttendanceQrBlock jobId={job.id} shift={s} portal={portal} />
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="col-span-12 lg:col-span-8 space-y-6">
          <div className="rounded-2xl border border-outline-variant/20 p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-on-surface">{t("job_detail_accepted_workers")}</h3>
              <p className="text-xs text-on-surface-variant">{workerTab === "accepted" ? acceptedWorkers.length : filteredAppliedWorkers.length}</p>
            </div>
            <div className="mb-4 flex flex-wrap gap-2">
              <button
                type="button"
                className={`rounded-md px-3 py-1 text-xs font-medium border ${workerTab === "accepted" ? "bg-surface-container border-outline-variant/40 text-on-surface" : "border-outline-variant/30 text-on-surface-variant"}`}
                onClick={() => setWorkerTab("accepted")}
              >
                Accepted
              </button>
              <button
                type="button"
                className={`rounded-md px-3 py-1 text-xs font-medium border ${workerTab === "applied" ? "bg-surface-container border-outline-variant/40 text-on-surface" : "border-outline-variant/30 text-on-surface-variant"}`}
                onClick={() => setWorkerTab("applied")}
              >
                Applied
              </button>
            </div>

            {workerTab === "applied" && (
              <div className="mb-4 grid gap-2 sm:grid-cols-3">
                <input
                  className="rounded-md border border-outline-variant/30 px-2 py-1.5 text-xs"
                  type="number"
                  min={0}
                  step="0.1"
                  placeholder="Min rating"
                  value={minRating}
                  onChange={(e) => setMinRating(e.target.value)}
                />
                <input
                  className="rounded-md border border-outline-variant/30 px-2 py-1.5 text-xs"
                  type="date"
                  value={appliedSince}
                  onChange={(e) => setAppliedSince(e.target.value)}
                />
                <input
                  className="rounded-md border border-outline-variant/30 px-2 py-1.5 text-xs"
                  type="number"
                  min={0}
                  placeholder="Min certifications"
                  value={minCerts}
                  onChange={(e) => setMinCerts(e.target.value)}
                />
                <input
                  className="rounded-md border border-outline-variant/30 px-2 py-1.5 text-xs"
                  type="number"
                  min={0}
                  step="0.1"
                  placeholder="Max distance (km)"
                  value={maxDistanceKm}
                  onChange={(e) => setMaxDistanceKm(e.target.value)}
                />
                <select
                  className="rounded-md border border-outline-variant/30 px-2 py-1.5 text-xs"
                  value={appliedSort}
                  onChange={(e) => setAppliedSort(e.target.value as "newest" | "oldest")}
                >
                  <option value="newest">Date applied: newest</option>
                  <option value="oldest">Date applied: oldest</option>
                </select>
                <label className="flex items-center gap-2 text-xs text-on-surface-variant">
                  <input type="checkbox" checked={preferredFirst} onChange={(e) => setPreferredFirst(e.target.checked)} />
                  {t("job_detail_preferred_first")}
                </label>
                <div className="sm:col-span-3 space-y-3">
                  <div>
                    <p className="text-[11px] font-medium text-on-surface-variant mb-1">{t("job_form_skills")}</p>
                    <SkillMultiPicker
                      t={t}
                      selected={skillFilters}
                      onChange={setSkillFilters}
                      jobRequiredLabels={job.required_skills}
                      inputClassName="w-full rounded-md border border-outline-variant/30 px-2 py-1.5 text-xs"
                      addButtonClassName="rounded-md border border-outline-variant/30 px-3 py-1.5 text-xs font-medium"
                      chipButtonClassName="rounded-md border border-outline-variant/30 px-2 py-1 text-[11px]"
                    />
                    {skillFilters.length > 0 && (
                      <button
                        type="button"
                        className="mt-1 text-xs text-primary hover:underline"
                        onClick={() => setSkillFilters([])}
                      >
                        {t("job_detail_clear_skill_filters")}
                      </button>
                    )}
                  </div>
                  <div>
                    <p className="text-[11px] font-medium text-on-surface-variant mb-1">{t("job_detail_filter_certs_label")}</p>
                    <CertificationMultiPicker
                      t={t}
                      selected={certFilters}
                      onChange={setCertFilters}
                      jobRequiredLabels={job.required_certifications}
                      inputClassName="w-full rounded-md border border-outline-variant/30 px-2 py-1.5 text-xs"
                      addButtonClassName="rounded-md border border-outline-variant/30 px-3 py-1.5 text-xs font-medium"
                      chipButtonClassName="rounded-md border border-outline-variant/30 px-2 py-1 text-[11px]"
                    />
                    {certFilters.length > 0 && (
                      <button
                        type="button"
                        className="mt-1 text-xs text-primary hover:underline"
                        onClick={() => setCertFilters([])}
                      >
                        {t("job_detail_clear_cert_filters")}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {(workerTab === "accepted" ? acceptedWorkers : filteredAppliedWorkers).length === 0 ? (
              <p className={emptyRoster}>{t("job_detail_no_accepted_yet")}</p>
            ) : (
              <ul className="divide-y divide-outline-variant/25">
                {(workerTab === "accepted" ? acceptedWorkers : filteredAppliedWorkers).map((w) => (
                  <li key={w.assignment_id} className="py-3 flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={rosterName}>{w.worker_name}</span>
                        <span className={assignmentBadgeClass(w.assignment_status)}>{assignmentLabel(w.assignment_status)}</span>
                        {w.is_preferred && <span className="text-[10px] rounded-full border border-outline-variant/30 px-2 py-0.5">Preferred</span>}
                      </div>
                      <p className="text-xs text-on-surface-variant mt-1">
                        {new Date(w.shift_starts_at).toLocaleString()} → {new Date(w.shift_ends_at).toLocaleString()}
                      </p>
                      <p className="text-[11px] text-on-surface-variant mt-1">
                        Rating {Number(w.rating_avg || 0).toFixed(1)} · Certs {w.certifications_count}
                        {w.applied_at ? ` · Applied ${new Date(w.applied_at).toLocaleString()}` : ""}
                      </p>
                      {(w.worker_skills?.length ?? 0) > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {(w.worker_skills ?? []).map((s) => (
                            <span
                              key={s}
                              title={requiredSkillSet.has(s) ? String(t("job_detail_filter_matches_job_requirement")) : undefined}
                              className={`text-[10px] px-1.5 py-0.5 rounded-md max-w-full truncate ${
                                requiredSkillSet.has(s)
                                  ? "bg-emerald-500/20 text-emerald-900 dark:text-emerald-100 font-semibold ring-1 ring-emerald-600/35"
                                  : "bg-surface-container-high text-on-surface-variant"
                              }`}
                            >
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                      {(w.worker_certifications?.length ?? 0) > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {(w.worker_certifications ?? []).map((c) => (
                            <span
                              key={c}
                              title={requiredCertSet.has(c) ? String(t("job_detail_filter_matches_job_requirement")) : undefined}
                              className={`text-[10px] px-1.5 py-0.5 rounded-md max-w-full truncate ${
                                requiredCertSet.has(c)
                                  ? "bg-emerald-500/20 text-emerald-900 dark:text-emerald-100 font-semibold ring-1 ring-emerald-600/35"
                                  : "bg-surface-container-high text-on-surface-variant"
                              }`}
                            >
                              {c}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                      {showEmployerActions && (w.assignment_status === "waitlisted" || w.assignment_status === "applied") && (
                        <button type="button" className={rosterActionBtn} disabled={actionBusy === w.assignment_id} onClick={() => promoteAssignment(w.assignment_id)}>
                          {w.assignment_status === "applied" ? t("job_detail_accept_application") : t("job_detail_promote_waitlist")}
                        </button>
                      )}
                      {showEmployerActions && w.assignment_status === "confirmed" && (
                        <button type="button" className={rosterActionBtn} disabled={actionBusy === w.assignment_id} onClick={() => moveToWaitlist(w.assignment_id)}>
                          {t("job_detail_move_to_waitlist")}
                        </button>
                      )}
                      {showEmployerActions && (w.assignment_status === "confirmed" || w.assignment_status === "waitlisted" || w.assignment_status === "applied") && (
                        <button type="button" className={rosterDangerBtn} disabled={actionBusy === w.assignment_id} onClick={() => rejectAssignment(w.assignment_id)}>
                          {t("job_detail_reject_worker")}
                        </button>
                      )}
                      <button type="button" className={profileLinkBtn} onClick={() => setProfileWorkerId(w.worker_profile_id)}>
                        {t("job_detail_view_profile")}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {(job.declined_workers.length > 0 || job.rejected_workers.length > 0) && (
            <details className="rounded-2xl border border-outline-variant/20 bg-surface-container-lowest/80 p-4">
              <summary className={detailsSummary}>
                {t("job_detail_declined_workers")} ({job.declined_workers.length}) · {t("job_detail_rejected_workers")} ({job.rejected_workers.length})
              </summary>
              <ul className="mt-3 space-y-2">
                {job.declined_workers.map((w) => (
                  <li key={w.offer_id} className="rounded-xl border border-outline-variant/20 p-3 flex items-center justify-between gap-3">
                    <div>
                      <span className={rosterName}>{w.worker_name}</span>
                      <p className={rosterMeta}>{new Date(w.shift_starts_at).toLocaleString()} → {new Date(w.shift_ends_at).toLocaleString()}</p>
                    </div>
                    <button type="button" className={profileLinkBtn} onClick={() => setProfileWorkerId(w.worker_profile_id)}>
                      {t("job_detail_view_profile")}
                    </button>
                  </li>
                ))}
                {job.rejected_workers.map((w) => (
                  <li key={w.assignment_id} className="rounded-xl border border-outline-variant/20 p-3 flex items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={rosterName}>{w.worker_name}</span>
                        <span className={assignmentBadgeClass("rejected")}>{assignmentLabel("rejected")}</span>
                      </div>
                      <p className={rosterMeta}>{new Date(w.shift_starts_at).toLocaleString()} → {new Date(w.shift_ends_at).toLocaleString()}</p>
                    </div>
                    <button type="button" className={profileLinkBtn} onClick={() => setProfileWorkerId(w.worker_profile_id)}>
                      {t("job_detail_view_profile")}
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          )}
          <div className="rounded-2xl border border-outline-variant/20 p-6">
            <h3 className="mb-4 text-xs font-black uppercase tracking-[0.2em] text-on-surface-variant">Activity Audit</h3>
            <div className="space-y-3 text-sm">
              <div className="rounded-lg border border-outline-variant/20 p-3">
                <p className="font-semibold">Order Created</p>
                <p className="text-on-surface-variant">#{job.id}</p>
              </div>
              {job.published_at && (
                <div className="rounded-lg border border-outline-variant/20 p-3">
                  <p className="font-semibold">Order Published</p>
                  <p className="text-on-surface-variant">{new Date(job.published_at).toLocaleString()}</p>
                </div>
              )}
              <div className="rounded-lg border border-outline-variant/20 p-3">
                <p className="font-semibold">Applications Snapshot</p>
                <p className="text-on-surface-variant">
                  {job.accepted_workers.length} active · {job.declined_workers.length} declined · {job.rejected_workers.length} rejected
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>

      {profileWorkerId !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="presentation"
          onClick={closeProfileModal}
        >
          <div
            role="dialog"
            aria-labelledby="worker-profile-title"
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-outline-variant/25 bg-surface-container-lowest p-6 text-on-surface shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between gap-2">
              <h2 id="worker-profile-title" className="font-headline text-xl font-extrabold">
                {t("job_detail_worker_profile")}
              </h2>
              <button type="button" onClick={closeProfileModal} className="rounded-lg px-2 py-1 text-sm font-semibold text-primary hover:bg-surface-container-high">
                {t("job_detail_close")}
              </button>
            </div>
            {profileLoading && <p className={emptyRoster}>{t("job_detail_profile_loading")}</p>}
            {profileErr && <p className={msgErr}>{profileErr}</p>}
            {profileData && !profileLoading && (
              <dl className="grid gap-3 text-sm">
                <div>
                  <dt className="text-on-surface-variant">{t("wizard_name")}</dt>
                  <dd className="font-medium">{profileData.full_name || "—"}</dd>
                </div>
                <div>
                  <dt className="text-on-surface-variant">{t("job_detail_profile_phone")}</dt>
                  <dd>{profileData.phone || "—"}</dd>
                </div>
                <div>
                  <dt className="text-on-surface-variant">{t("job_detail_profile_email")}</dt>
                  <dd>{profileData.email ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-on-surface-variant">{t("job_detail_profile_tier")}</dt>
                  <dd>{profileData.tier}</dd>
                </div>
                <div>
                  <dt className="text-on-surface-variant">{t("job_detail_profile_rating")}</dt>
                  <dd>{Number(profileData.rating_avg).toFixed(1)}</dd>
                </div>
                <div>
                  <dt className="text-on-surface-variant">{t("job_detail_profile_status")}</dt>
                  <dd>{profileData.status}</dd>
                </div>
                <div>
                  <dt className="text-on-surface-variant">{t("job_detail_profile_languages")}</dt>
                  <dd>{profileData.languages?.length ? profileData.languages.join(", ") : "—"}</dd>
                </div>
                <div>
                  <dt className="text-on-surface-variant">{t("job_detail_profile_job_types")}</dt>
                  <dd>{profileData.job_type_preferences?.length ? profileData.job_type_preferences.join(", ") : "—"}</dd>
                </div>
                <div>
                  <dt className="text-on-surface-variant">{t("job_detail_profile_skills")}</dt>
                  <dd className="mt-1">
                    {profileData.skills?.length ? (
                      <div className="flex flex-wrap gap-1">
                        {profileData.skills.map((s) => (
                          <span
                            key={s}
                            className={`text-xs px-2 py-0.5 rounded-md ${
                              requiredSkillSet.has(s)
                                ? "bg-emerald-500/20 font-semibold ring-1 ring-emerald-600/35"
                                : "bg-surface-container-high"
                            }`}
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    ) : (
                      "—"
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-on-surface-variant">{t("job_detail_profile_certs")}</dt>
                  <dd className="mt-1">
                    {profileData.certifications?.length ? (
                      <div className="flex flex-wrap gap-1">
                        {profileData.certifications.map((c) => (
                          <span
                            key={c}
                            className={`text-xs px-2 py-0.5 rounded-md ${
                              requiredCertSet.has(c)
                                ? "bg-emerald-500/20 font-semibold ring-1 ring-emerald-600/35"
                                : "bg-surface-container-high"
                            }`}
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    ) : (
                      "—"
                    )}
                  </dd>
                </div>
              </dl>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
