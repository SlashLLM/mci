import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { Link, Navigate, Outlet, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, apiUrl, getToken } from "../../api";
import { JobTypeMultiPicker } from "../../components/jobTypes/JobTypeMultiPicker";
import { ClockSiteMap } from "../../components/maps/ClockSiteMap";
import { DEFAULT_MAP_CENTER, LocationMapPicker } from "../../components/maps/LocationMapPicker";
import { CertificationMultiPicker } from "../../components/certifications/CertificationMultiPicker";
import { SkillMultiPicker } from "../../components/skills/SkillMultiPicker";
import { isAllowedJobType, JOB_TYPES } from "../../constants/jobTypes";
import WorkerPortalLayout from "../../components/worker/WorkerPortalLayout";
import WorkerOnboardingPage from "./WorkerOnboardingPage";

function MatIcon({ name, className = "" }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`.trim()}>{name}</span>;
}

function fmtDate(iso: string) {
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function fmtMoney(n: number) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(n);
}

type ClockNoticeKind = "error" | "warning" | "success" | "info";

/** Map FastAPI `detail` (string, object, or list) to a worker-facing message. */
function parseQrClockApiError(
  body: Record<string, unknown> | null,
  fallbackText: string,
  resStatusText: string,
  t: TFunction,
): { text: string; kind: ClockNoticeKind } {
  const raw = body?.detail;
  if (raw == null) {
    return { text: fallbackText || resStatusText, kind: "error" };
  }
  if (typeof raw === "string") {
    return { text: raw, kind: "error" };
  }
  if (typeof raw === "object" && !Array.isArray(raw)) {
    const o = raw as { code?: string; message?: string; distance_m?: number | null; radius_m?: number };
    if (o.code === "geofence_clock_in_blocked") {
      const text =
        o.distance_m != null && o.radius_m != null
          ? t("clock_page_geofence_blocked", {
              distance: Math.round(o.distance_m),
              radius: o.radius_m,
            })
          : t("clock_page_geofence_blocked_generic");
      return { text, kind: "warning" };
    }
    if (o.code === "clock_in_grace_expired") {
      return { text: t("clock_page_grace_expired"), kind: "warning" };
    }
    if (typeof o.message === "string") {
      return { text: o.message, kind: "error" };
    }
  }
  if (Array.isArray(raw)) {
    return { text: JSON.stringify(raw), kind: "error" };
  }
  return { text: fallbackText || resStatusText, kind: "error" };
}

type OfferRow = {
  id: number;
  match_score?: number | null;
  expires_at?: string | null;
  shift: {
    id: number;
    starts_at: string;
    ends_at: string;
    job_title: string;
    job_id: number;
  };
};

type MarketplaceShift = {
  shift_id: number;
  job_id: number;
  title: string;
  job_type: string;
  starts_at: string;
  ends_at: string;
  location_address?: string | null;
  location_lat?: number | null;
  location_lng?: number | null;
  hourly_rate?: number | null;
  per_shift_rate?: number | null;
  distance_m?: number | null;
  pending_offer_id?: number | null;
  my_application_status?: "applied" | null;
};

type AssignmentRow = {
  assignment_id: number;
  status: string;
  shift: { id: number; starts_at: string; ends_at: string; job_title: string };
};

type TimesheetRow = {
  id: number;
  gross_pay: number;
  status: string;
  job_title?: string | null;
  shift_date?: string | null;
  shift_starts_at?: string | null;
  shift_ends_at?: string | null;
  clock_in_at?: string | null;
  clock_out_at?: string | null;
};

function localDateYmd(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function timesheetRowYmd(x: TimesheetRow): string | null {
  if (x.shift_date) return x.shift_date;
  if (x.shift_starts_at) return x.shift_starts_at.slice(0, 10);
  return null;
}

const CARD_IMAGES = [
  "https://lh3.googleusercontent.com/aida-public/AB6AXuA20B4ehqrtncvnYyi0LDDRUZKR2CTz60StntahrGjPgQKihGi0MVG0K7kZIwXbPUIIDIA5LbpmmrzFlkQ6Pii8sTUNtlu3cWBE5ur6PuGotbOjdHGurS7RrVxoim6oHROMct58MfwgQMlIcAgxIH6w7is2gbFfRko64TfQgXVN1Zcqa99vhXhU1pPYLkVdCKydExpy8Z7o82NwnqDmkp7P8lVuhRbv8nSL4dIz0ULfJRGRlp_Sht0byb2kBP2AdcT_u0tSgirzVWs",
  "https://lh3.googleusercontent.com/aida-public/AB6AXuBuweTe7dDAAkVlBxPLKvxTmDxnNs5FjL5LYJhDXsrDIYX4S3uUjPHfyrgIegzYF265KP4EjaL3EAlrOJnJiMB0rVCLV_do9UXspSbiO4mxk_n29zi4WyKis4Oai3tWEKamw8iEi_jL9pIbAs-dyP9k6RLNcyVZsCDBNZbu1MnQCk1a4xvt4nZnbCTxLkQNYn9uUvCqItaWaX7Upwo6QAAUK51yt0vkJJTKS7OGDdLtkxKlADXC1hy95DWrXIXQtzrXWO_45FMILLE",
  "https://lh3.googleusercontent.com/aida-public/AB6AXuCotMEzE675eEbcqRz39cB9lwL2d29M_Aaw9ke-U8Xi0utjWm6PHEfVDwm5hbJN_4uRX8PutiCtuSZhblQzwYBfUOZW5MCPXYcyR-KOMyeWSjgChybHZKdrKr-cUluyMRg31ZH5t2p8shb4NtSR-y8BVzdspFJpVGZ0swJTzHjEDWLgrbRKlbkrwoPgcgl0FiV21fyGpY44eNlcJhkmWVWKSVAiaWN2YO_3ca560QiQ0hbzgf_AUDwre5TzLECNBeO2j_o_T5kgWao",
];

function rateLabel(s: MarketplaceShift): string {
  if (s.hourly_rate != null && s.hourly_rate > 0) return `${fmtMoney(s.hourly_rate)}/hr`;
  if (s.per_shift_rate != null && s.per_shift_rate > 0) return `${fmtMoney(s.per_shift_rate)}/shift`;
  return "—";
}

function fmtDistanceKm(distanceM: number | null | undefined, t: TFunction): string | null {
  if (distanceM == null || !Number.isFinite(distanceM)) return null;
  const km = distanceM / 1000;
  const rounded = km >= 100 ? Math.round(km) : Math.round(km * 10) / 10;
  return t("marketplace_distance_km_one", { km: rounded });
}

function PageHeader({
  eyebrow,
  title,
  description,
  extra,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  extra?: ReactNode;
}) {
  return (
    <header className="mb-12 flex flex-col justify-between gap-6 md:flex-row md:items-end">
      <div className="space-y-2">
        <span className="text-xs font-bold uppercase tracking-[0.2em] text-primary">{eyebrow}</span>
        <h1 className="font-headline text-4xl font-extrabold tracking-tight text-on-background md:text-5xl">{title}</h1>
        {description ? <p className="max-w-md text-on-surface-variant">{description}</p> : null}
      </div>
      {extra}
    </header>
  );
}

function PendingPayoutCard({ amount }: { amount: number }) {
  return (
    <div className="flex items-center gap-4 rounded-xl bg-surface-container-low px-6 py-4">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-container">
        <MatIcon name="account_balance_wallet" className="text-on-primary-container" />
      </div>
      <div>
        <p className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">Pending Payout</p>
        <p className="font-headline text-xl font-bold">{fmtMoney(amount)}</p>
      </div>
    </div>
  );
}

function OffersHome() {
  const { t } = useTranslation();
  const [offers, setOffers] = useState<OfferRow[]>([]);
  const [marketplace, setMarketplace] = useState<MarketplaceShift[]>([]);
  const [timesheets, setTimesheets] = useState<TimesheetRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api<OfferRow[]>("/worker/offers").catch(() => [] as OfferRow[]),
      api<MarketplaceShift[]>("/worker/marketplace/shifts").catch(() => [] as MarketplaceShift[]),
      api<TimesheetRow[]>("/timesheets").catch(() => [] as TimesheetRow[]),
    ])
      .then(([o, m, ts]) => {
        if (!cancelled) {
          setOffers(o);
          setMarketplace(m);
          setTimesheets(ts);
        }
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const pendingPayout = useMemo(() => {
    return timesheets.filter((x) => x.status !== "payment_released").reduce((s, x) => s + (x.gross_pay || 0), 0);
  }, [timesheets]);

  async function accept(id: number) {
    await api(`/worker/offers/${id}/accept`, { method: "POST" });
    const r = await api<OfferRow[]>("/worker/offers");
    setOffers(r);
  }

  const featured = offers[0];
  const nearYou = marketplace.slice(0, 3);
  const gridShifts = marketplace.slice(0, 6);

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 md:px-8">
      <PageHeader
        eyebrow="Editorial Overview"
        title={t("my_offers")}
        description="Review and accept curated shift opportunities tailored to your expertise and site availability."
        extra={<PendingPayoutCard amount={pendingPayout} />}
      />
      {err && <p className="mb-6 text-sm text-error">{err}</p>}

      <section className="mb-16 grid grid-cols-1 gap-8 lg:grid-cols-12">
        <div className="relative overflow-hidden rounded-[2rem] border border-outline-variant/10 bg-surface-container-lowest p-8 shadow-sm transition-all duration-500 hover:shadow-xl md:p-10 lg:col-span-8">
          <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-primary-container/20 blur-3xl" />
          <div className="relative z-10">
            {featured ? (
              <>
                <div className="mb-12 flex flex-wrap items-start justify-between gap-4">
                  <span className="rounded-full bg-tertiary-container px-4 py-1.5 text-xs font-bold uppercase tracking-widest text-on-tertiary-container">
                    High Priority
                  </span>
                  {featured.match_score != null && (
                    <span className="text-4xl font-black text-primary">
                      {Number(featured.match_score).toFixed(1)}
                      <span className="ml-1 text-sm font-medium text-on-surface-variant">match</span>
                    </span>
                  )}
                </div>
                <div className="mb-8">
                  <h3 className="mb-2 font-headline text-2xl font-extrabold md:text-3xl">{featured.shift.job_title}</h3>
                  <div className="flex flex-wrap items-center gap-4 text-on-surface-variant">
                    <span className="flex items-center gap-1">
                      <MatIcon name="location_on" className="text-sm" />
                      Job #{featured.shift.job_id}
                    </span>
                    <span className="flex items-center gap-1">
                      <MatIcon name="calendar_today" className="text-sm" />
                      {fmtDate(featured.shift.starts_at)} — {fmtDate(featured.shift.ends_at)}
                    </span>
                  </div>
                </div>
                <div className="mb-10 grid grid-cols-1 gap-8 md:grid-cols-2">
                  <div className="space-y-4">
                    <h4 className="text-[10px] font-bold uppercase tracking-widest text-primary">Details</h4>
                    <ul className="space-y-2 text-sm text-on-surface">
                      <li className="flex items-start gap-2">
                        <MatIcon name="check_circle" className="text-lg text-primary" />
                        Shift ID {featured.shift.id}
                      </li>
                      {featured.expires_at && (
                        <li className="flex items-start gap-2">
                          <MatIcon name="schedule" className="text-lg text-primary" />
                          Expires {fmtDate(featured.expires_at)}
                        </li>
                      )}
                    </ul>
                  </div>
                  <div className="space-y-4">
                    <h4 className="text-[10px] font-bold uppercase tracking-widest text-primary">Window</h4>
                    <div className="rounded-xl border border-outline-variant/10 bg-surface-container-low p-4">
                      <p className="mb-1 text-xs font-semibold">Scheduled</p>
                      <p className="text-sm text-on-surface-variant">
                        {new Date(featured.shift.starts_at).toLocaleTimeString(undefined, { timeStyle: "short" })} —{" "}
                        {new Date(featured.shift.ends_at).toLocaleTimeString(undefined, { timeStyle: "short" })}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-4">
                  <button
                    type="button"
                    className="flex-1 rounded-xl bg-primary px-8 py-4 font-bold text-on-primary shadow-lg shadow-primary/20 transition-all hover:bg-primary-dim active:scale-95 md:flex-none"
                    onClick={() => accept(featured.id)}
                  >
                    Accept Shift
                  </button>
                  <Link
                    to="/worker/marketplace"
                    className="flex-1 rounded-xl bg-surface-container-high px-8 py-4 text-center font-bold text-on-surface transition-all hover:bg-surface-variant active:scale-95 md:flex-none"
                  >
                    View Details
                  </Link>
                </div>
              </>
            ) : (
              <div className="py-8 text-center">
                <p className="mb-6 text-on-surface-variant">No pending offers right now.</p>
                <Link
                  to="/worker/marketplace"
                  className="inline-flex rounded-xl bg-primary px-8 py-4 font-bold text-on-primary shadow-lg shadow-primary/20 hover:bg-primary-dim"
                >
                  Browse marketplace
                </Link>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-6 lg:col-span-4">
          <div className="flex-1 rounded-[1.5rem] bg-surface-container-low p-8">
            <h4 className="mb-6 text-xs font-bold uppercase tracking-widest text-primary">Upcoming Near You</h4>
            <div className="space-y-6">
              {nearYou.length === 0 && <p className="text-sm text-on-surface-variant">No recommended shifts yet.</p>}
              {nearYou.map((s, i) => (
                <div key={s.shift_id}>
                  {i > 0 && <div className="mb-6 h-px bg-outline-variant/10" />}
                  <Link to="/worker/marketplace" className="group block cursor-pointer">
                    <div className="mb-2 flex justify-between gap-2">
                      <p className="text-lg font-bold transition-colors group-hover:text-primary">{s.title}</p>
                      <span className="shrink-0 font-bold text-primary">{rateLabel(s)}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-on-surface-variant">
                      <span className="truncate">{s.location_address || s.job_type}</span>
                      <span>•</span>
                      <span>{fmtDate(s.starts_at)}</span>
                    </div>
                  </Link>
                </div>
              ))}
            </div>
            <Link
              to="/worker/marketplace"
              className="mt-8 flex w-full justify-center rounded-xl border border-primary/20 py-3 text-sm font-bold text-primary transition-colors hover:bg-primary/5"
            >
              {marketplace.length > 3 ? `Browse ${marketplace.length - 3} More` : "Browse marketplace"}
            </Link>
          </div>

          <div className="group relative overflow-hidden rounded-[1.5rem] bg-primary p-8 text-on-primary">
            <div className="absolute -bottom-4 -right-4 opacity-10 transition-transform duration-700 group-hover:scale-110">
              <MatIcon name="explore" className="text-[120px]" />
            </div>
            <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em]">Marketplace</p>
            <h4 className="mb-4 font-headline text-2xl font-bold">Explore New Industries</h4>
            <p className="mb-6 text-sm leading-relaxed text-primary-fixed/90">
              Diversify your portfolio. New shifts in specialized tech and logistics are updated regularly.
            </p>
            <Link to="/worker/marketplace" className="flex items-center gap-2 text-sm font-bold transition-all hover:gap-4">
              Go to Marketplace <MatIcon name="arrow_forward" />
            </Link>
          </div>
        </div>
      </section>

      <MarketplaceSection shifts={gridShifts} showTitle />
    </div>
  );
}

function MarketplaceSection({
  shifts,
  showTitle,
  maxKm,
  onMaxKmChange,
  locationHint,
}: {
  shifts: MarketplaceShift[];
  showTitle?: boolean;
  maxKm?: string;
  onMaxKmChange?: (v: string) => void;
  locationHint?: ReactNode;
}) {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const [jobTypeFilter, setJobTypeFilter] = useState("");
  const detailPath = (s: MarketplaceShift) => `/worker/marketplace/${s.shift_id}`;
  const filtered = useMemo(() => {
    const qq = q.trim().toLowerCase();
    return shifts.filter((s) => {
      if (jobTypeFilter && s.job_type !== jobTypeFilter) return false;
      if (!qq) return true;
      return s.title.toLowerCase().includes(qq) || s.job_type.toLowerCase().includes(qq);
    });
  }, [shifts, q, jobTypeFilter]);

  const filterSelectClass =
    "min-w-[12rem] rounded-xl border-none bg-surface-container py-3 px-3 text-sm text-on-surface focus:ring-2 focus:ring-primary";

  return (
    <section className={showTitle ? "mb-20" : ""}>
      {showTitle && (
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="font-headline text-3xl font-extrabold tracking-tight">Marketplace</h2>
          <div className="flex flex-wrap items-end gap-2">
            {onMaxKmChange != null && maxKm != null && (
              <label className="flex flex-col gap-1 text-xs text-on-surface-variant">
                <span>{t("marketplace_max_km_label")}</span>
                <input
                  type="number"
                  min={0}
                  step={1}
                  placeholder={t("marketplace_max_km_placeholder")}
                  className="w-28 rounded-xl border-none bg-surface-container py-2 px-3 text-sm text-on-surface focus:ring-2 focus:ring-primary"
                  value={maxKm}
                  onChange={(e) => onMaxKmChange(e.target.value)}
                />
              </label>
            )}
            <label className="flex flex-col gap-1 text-xs text-on-surface-variant">
              <span>{t("marketplace_job_type_filter")}</span>
              <select
                className={filterSelectClass}
                value={jobTypeFilter}
                onChange={(e) => setJobTypeFilter(e.target.value)}
              >
                <option value="">{t("marketplace_job_type_all")}</option>
                {JOB_TYPES.map((jt) => (
                  <option key={jt} value={jt}>
                    {jt}
                  </option>
                ))}
              </select>
            </label>
            <div className="relative">
              <MatIcon
                name="search"
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant"
              />
              <input
                className="w-full min-w-[12rem] rounded-xl border-none bg-surface-container py-3 pl-12 pr-6 text-sm text-on-surface focus:ring-2 focus:ring-primary sm:w-64"
                placeholder={t("marketplace_search_placeholder")}
                type="search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>
          </div>
        </div>
      )}
      {!showTitle && (
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="font-headline text-2xl font-extrabold tracking-tight">{t("marketplace")}</h2>
          <div className="flex flex-wrap items-end gap-3">
            {onMaxKmChange != null && maxKm != null && (
              <label className="flex flex-col gap-1 text-xs text-on-surface-variant">
                <span>{t("marketplace_max_km_label")}</span>
                <input
                  type="number"
                  min={0}
                  step={1}
                  placeholder={t("marketplace_max_km_placeholder")}
                  className="w-28 rounded-xl border-none bg-surface-container py-2 px-3 text-sm text-on-surface focus:ring-2 focus:ring-primary"
                  value={maxKm}
                  onChange={(e) => onMaxKmChange(e.target.value)}
                />
              </label>
            )}
            <label className="flex flex-col gap-1 text-xs text-on-surface-variant">
              <span>{t("marketplace_job_type_filter")}</span>
              <select
                className={filterSelectClass}
                value={jobTypeFilter}
                onChange={(e) => setJobTypeFilter(e.target.value)}
              >
                <option value="">{t("marketplace_job_type_all")}</option>
                {JOB_TYPES.map((jt) => (
                  <option key={jt} value={jt}>
                    {jt}
                  </option>
                ))}
              </select>
            </label>
            <div className="relative max-w-md flex-1">
            <MatIcon
              name="search"
              className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant"
            />
            <input
              className="w-full rounded-xl border-none bg-surface-container py-3 pl-12 pr-6 text-sm text-on-surface focus:ring-2 focus:ring-primary"
              placeholder={t("marketplace_search_placeholder")}
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          </div>
        </div>
      )}
      {locationHint && <p className="mb-4 text-sm text-on-surface-variant">{locationHint}</p>}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {filtered.map((s, i) => {
          const distLabel = fmtDistanceKm(s.distance_m, t);
          return (
          <Link
            key={s.shift_id}
            to={detailPath(s)}
            className="block overflow-hidden rounded-2xl border border-outline-variant/10 bg-surface-container-lowest text-left transition-all duration-300 hover:shadow-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            <div className="relative h-40">
              <img
                alt=""
                className="h-full w-full object-cover"
                src={CARD_IMAGES[i % CARD_IMAGES.length]}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
              <div className="absolute bottom-4 left-4 right-4 flex items-end justify-between gap-2">
                <span className="rounded bg-white/20 px-2 py-1 text-[10px] font-bold uppercase text-white backdrop-blur-md">
                  {s.job_type || "Shift"}
                </span>
                <span className="font-bold text-white">{rateLabel(s)}</span>
              </div>
            </div>
            <div className="p-6">
              <h5 className="mb-2 text-lg font-bold">{s.title}</h5>
              {distLabel && <p className="mb-2 text-xs font-semibold text-primary">{distLabel}</p>}
              <p className="mb-6 line-clamp-2 text-xs text-on-surface-variant">
                {s.location_address || `Starts ${fmtDate(s.starts_at)}`}
              </p>
              <div className="flex items-center justify-between border-t border-outline-variant/10 pt-4">
                <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-tighter text-on-surface-variant">
                  <MatIcon name="schedule" className="text-sm" />
                  {fmtDate(s.starts_at)}
                </span>
                <span className="flex items-center gap-1 text-sm font-bold text-primary">
                  Details <MatIcon name="chevron_right" className="text-sm" />
                </span>
              </div>
            </div>
          </Link>
          );
        })}
      </div>
      {filtered.length === 0 && <p className="mt-8 text-center text-on-surface-variant">No shifts match your search.</p>}
    </section>
  );
}

function MarketplacePage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<MarketplaceShift[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [maxKm, setMaxKm] = useState("");

  useEffect(() => {
    let cancelled = false;
    const v = maxKm.trim();
    const n = v === "" ? NaN : parseFloat(v);
    const suffix =
      v !== "" && Number.isFinite(n) && n > 0 ? `?max_km=${encodeURIComponent(String(n))}` : "";
    setErr(null);
    api<MarketplaceShift[]>(`/worker/marketplace/shifts${suffix}`)
      .then((r) => {
        if (!cancelled) {
          setRows(r);
          setErr(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [maxKm]);

  const locationHint =
    rows.length > 0 && rows.every((s) => s.distance_m == null) ? (
      <p className="mb-4 text-sm text-on-surface-variant">
        {t("marketplace_set_location_hint_prefix")}{" "}
        <Link to="/worker/profile?tab=account" className="font-semibold text-primary underline underline-offset-2">
          {t("profile")}
        </Link>
        {t("marketplace_set_location_hint_suffix")}
      </p>
    ) : null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 md:px-8">
      <PageHeader
        eyebrow="Open roles"
        title={t("marketplace")}
        description="Search and review shifts matched to your profile. Apply from your offers when employers send them."
      />
      {err && <p className="mb-6 text-sm text-error">{err}</p>}
      <MarketplaceSection shifts={rows} maxKm={maxKm} onMaxKmChange={setMaxKm} locationHint={locationHint} />
    </div>
  );
}

function fmtTime(iso: string) {
  try {
    return new Intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function MarketplaceShiftDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { shiftId } = useParams<{ shiftId: string }>();
  const id = shiftId ? Number.parseInt(shiftId, 10) : NaN;
  const [rows, setRows] = useState<MarketplaceShift[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  function reloadShifts() {
    return api<MarketplaceShift[]>("/worker/marketplace/shifts").then(setRows);
  }

  useEffect(() => {
    let cancelled = false;
    api<MarketplaceShift[]>("/worker/marketplace/shifts")
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const shift = Number.isFinite(id) ? rows.find((s) => s.shift_id === id) : undefined;
  const hasApplied = shift?.my_application_status === "applied";

  async function handleApply() {
    if (!shift) return;
    setActionErr(null);
    setActionBusy(true);
    try {
      await api(`/worker/marketplace/shifts/${shift.shift_id}/apply`, { method: "POST" });
      await reloadShifts();
    } catch (e) {
      setActionErr(String(e));
    } finally {
      setActionBusy(false);
    }
  }

  async function handleDeclineListing() {
    if (!shift) return;
    setActionErr(null);
    setActionBusy(true);
    try {
      if (hasApplied) {
        await api(`/worker/marketplace/shifts/${shift.shift_id}/withdraw-application`, { method: "POST" });
        await reloadShifts();
      } else {
        await api(`/worker/marketplace/shifts/${shift.shift_id}/dismiss`, { method: "POST" });
      }
      navigate("/worker/marketplace");
    } catch (e) {
      setActionErr(String(e));
    } finally {
      setActionBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 md:px-8">
      <Link
        to="/worker/marketplace"
        className="mb-8 inline-flex items-center gap-2 text-sm font-bold text-primary transition-colors hover:text-primary-dim"
      >
        <MatIcon name="arrow_back" className="text-lg" />
        {t("marketplace")}
      </Link>

      {loading && <p className="text-on-surface-variant">Loading…</p>}
      {err && !loading && <p className="text-sm text-error">{err}</p>}
      {!loading && !err && !shift && (
        <div className="rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-8">
          <p className="text-on-surface-variant">
            This shift is not available in your marketplace list anymore. It may have been filled or updated.
          </p>
          <Link
            to="/worker/marketplace"
            className="mt-6 inline-flex rounded-xl bg-primary px-6 py-3 font-bold text-on-primary hover:bg-primary-dim"
          >
            Back to marketplace
          </Link>
        </div>
      )}
      {shift && (
        <article className="overflow-hidden rounded-2xl border border-outline-variant/10 bg-surface-container-lowest shadow-sm">
          <div className="border-b border-outline-variant/10 bg-surface-container-low px-6 py-4">
            <span className="rounded-full bg-primary-container px-3 py-1 text-xs font-bold uppercase tracking-wider text-on-primary-container">
              {shift.job_type || "Shift"}
            </span>
            <h1 className="mt-4 font-headline text-3xl font-extrabold tracking-tight">{shift.title}</h1>
            <p className="mt-2 text-2xl font-bold text-primary">{rateLabel(shift)}</p>
          </div>
          <div className="space-y-6 p-6">
            {fmtDistanceKm(shift.distance_m, t) && (
              <p className="text-sm font-semibold text-primary">{fmtDistanceKm(shift.distance_m, t)}</p>
            )}
            {shift.location_address && (
              <div>
                <h2 className="mb-2 text-[10px] font-bold uppercase tracking-widest text-primary">Location</h2>
                <p className="flex items-start gap-2 text-on-surface">
                  <MatIcon name="location_on" className="text-lg text-on-surface-variant" />
                  {shift.location_address}
                </p>
              </div>
            )}
            <div>
              <h2 className="mb-2 text-[10px] font-bold uppercase tracking-widest text-primary">Schedule</h2>
              <ul className="space-y-2 text-sm text-on-surface">
                <li className="flex flex-wrap items-center gap-2">
                  <MatIcon name="calendar_today" className="text-on-surface-variant" />
                  <span>
                    {fmtDate(shift.starts_at)} — {fmtDate(shift.ends_at)}
                  </span>
                </li>
                <li className="flex flex-wrap items-center gap-2 text-on-surface-variant">
                  <MatIcon name="schedule" className="text-on-surface-variant" />
                  <span>
                    {fmtTime(shift.starts_at)} – {fmtTime(shift.ends_at)}
                  </span>
                </li>
              </ul>
            </div>
            <div>
              <h2 className="mb-2 text-[10px] font-bold uppercase tracking-widest text-primary">Job</h2>
              <p className="text-sm text-on-surface-variant">
                Job order #{shift.job_id} · Shift #{shift.shift_id}
              </p>
            </div>
            {actionErr && <p className="text-sm text-error">{actionErr}</p>}
            {hasApplied && (
              <p className="rounded-xl bg-amber-50 p-4 text-sm text-amber-950 dark:bg-amber-900/30 dark:text-amber-100">
                {t("marketplace_detail_applied_pending")}
              </p>
            )}
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              {!hasApplied ? (
                <button
                  type="button"
                  disabled={actionBusy}
                  onClick={handleApply}
                  className="rounded-xl bg-primary px-6 py-3 font-bold text-on-primary hover:bg-primary-dim disabled:opacity-50"
                >
                  {t("marketplace_detail_apply")}
                </button>
              ) : null}
              <button
                type="button"
                disabled={actionBusy}
                onClick={handleDeclineListing}
                className="rounded-xl border border-outline-variant/40 bg-surface-container-low px-6 py-3 font-bold text-on-surface hover:bg-surface-container disabled:opacity-50"
              >
                {hasApplied ? t("marketplace_detail_withdraw_application") : t("marketplace_detail_decline_listing")}
              </button>
            </div>
            <p className="rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant">
              {t("marketplace_detail_apply_hint")}
            </p>
            {shift.pending_offer_id != null && shift.pending_offer_id > 0 && (
              <p className="text-xs text-on-surface-variant">
                {t("marketplace_detail_offer_also_sent")}{" "}
                <Link to="/worker" className="font-semibold text-primary underline">
                  {t("my_offers")}
                </Link>
              </p>
            )}
          </div>
        </article>
      )}
    </div>
  );
}

type HistoryRow = {
  assignment_id: number;
  status: string;
  history_bucket: string;
  waitlist_rank: number | null;
  job_id: number;
  job_title: string;
  job_type: string;
  location_address: string;
  shift: { id: number; starts_at: string; ends_at: string };
};

function HistoryPage() {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<"all" | "accepted" | "waitlisted" | "pending" | "rejected">("all");
  const [rows, setRows] = useState<HistoryRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    api<HistoryRow[]>(`/worker/history?status=${encodeURIComponent(filter)}`)
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filter]);

  function bucketBadgeClass(bucket: string) {
    if (bucket === "accepted")
      return "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200";
    if (bucket === "waitlisted")
      return "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200";
    if (bucket === "pending")
      return "bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200";
    if (bucket === "rejected")
      return "bg-rose-100 text-rose-900 dark:bg-rose-900/40 dark:text-rose-200";
    return "bg-surface-container-high text-on-surface";
  }

  const filters: ("all" | "accepted" | "waitlisted" | "pending" | "rejected")[] = [
    "all",
    "accepted",
    "waitlisted",
    "pending",
    "rejected",
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 md:px-8">
      <PageHeader
        eyebrow={t("worker_history_eyebrow")}
        title={t("worker_history_title")}
        description={t("worker_history_description")}
      />
      {err && <p className="mb-6 text-sm text-error">{err}</p>}
      <div className="mb-8 flex flex-wrap gap-2">
        {filters.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
              filter === f
                ? "bg-primary text-on-primary shadow-md"
                : "bg-surface-container-high text-on-surface hover:bg-surface-variant"
            }`}
          >
            {t(`worker_history_filter_${f}`)}
          </button>
        ))}
      </div>
      {loading && <p className="text-on-surface-variant">{t("job_detail_profile_loading")}</p>}
      {!loading && (
        <ul className="space-y-4">
          {rows.map((row) => (
            <li
              key={row.assignment_id}
              className="flex flex-col gap-3 rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-6 shadow-sm sm:flex-row sm:items-start sm:justify-between"
            >
              <div className="min-w-0 flex-1">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <p className="font-headline text-lg font-bold">{row.job_title}</p>
                  <span
                    className={`inline-flex rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide ${bucketBadgeClass(row.history_bucket)}`}
                  >
                    {t(`worker_history_bucket_${row.history_bucket}`)}
                  </span>
                </div>
                <p className="text-sm text-on-surface-variant">{row.job_type}</p>
                <p className="mt-1 flex flex-wrap items-center gap-1 text-sm text-on-surface-variant">
                  <MatIcon name="location_on" className="text-base" />
                  <span className="break-words">{row.location_address}</span>
                </p>
                <p className="mt-2 text-sm text-on-surface-variant">
                  <MatIcon name="calendar_today" className="mr-1 inline text-base align-text-bottom" />
                  {fmtDate(row.shift.starts_at)} — {fmtDate(row.shift.ends_at)}
                </p>
                <p className="mt-1 text-xs text-on-surface-variant">
                  {t("worker_history_assignment_id", { id: row.assignment_id })} · {t("worker_history_job_id", { id: row.job_id })} ·{" "}
                  {t("worker_history_shift_id", { id: row.shift.id })}
                </p>
                {row.waitlist_rank != null && (row.history_bucket === "waitlisted" || row.history_bucket === "pending") && (
                  <p className="mt-1 text-xs font-semibold text-amber-800 dark:text-amber-200">
                    {t("worker_history_waitlist_rank", { rank: row.waitlist_rank })}
                  </p>
                )}
              </div>
              <Link
                to={`/worker/marketplace/${row.shift.id}`}
                className="inline-flex shrink-0 items-center gap-1 text-sm font-bold text-primary hover:text-primary-dim"
              >
                {t("worker_history_view_shift")} <MatIcon name="chevron_right" className="text-lg" />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {!loading && rows.length === 0 && !err && (
        <p className="text-center text-on-surface-variant">{t("worker_history_empty")}</p>
      )}
    </div>
  );
}

function ShiftsPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<AssignmentRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api<AssignmentRow[]>("/worker/my-shifts")
      .then(setRows)
      .catch((e) => setErr(String(e)));
  }, []);
  return (
    <div className="mx-auto max-w-7xl px-4 py-10 md:px-8">
      <PageHeader
        eyebrow="Schedule"
        title={t("my_shifts")}
        description={t("my_shifts_description")}
      />
      {err && <p className="mb-6 text-sm text-error">{err}</p>}
      <ul className="space-y-4">
        {rows.map((s) => (
          <li
            key={s.assignment_id}
            className="flex flex-col gap-3 rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-6 shadow-sm sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <p className="font-headline text-lg font-bold">{s.shift.job_title}</p>
              <p className="text-sm text-on-surface-variant">
                {fmtDate(s.shift.starts_at)} — {fmtDate(s.shift.ends_at)}
              </p>
              <p className="mt-1 text-xs text-on-surface-variant">Assignment #{s.assignment_id}</p>
            </div>
            <div className="flex flex-col items-stretch gap-2 sm:items-end">
              {s.status === "confirmed" && (
                <Link
                  to={`/worker/clock?assignment=${s.assignment_id}`}
                  className="inline-flex justify-center rounded-xl bg-primary px-4 py-2 text-center text-sm font-semibold text-on-primary hover:bg-primary-dim"
                >
                  {t("my_shifts_clock_in")}
                </Link>
              )}
              <span className="inline-flex w-fit rounded-full bg-primary-container px-4 py-1.5 text-sm font-semibold text-on-primary-container">
                {s.status === "applied" ? t("worker_history_bucket_pending") : s.status}
              </span>
            </div>
          </li>
        ))}
      </ul>
      {rows.length === 0 && !err && <p className="text-on-surface-variant">No assignments yet.</p>}
    </div>
  );
}

function EarningsPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<TimesheetRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [periodFrom, setPeriodFrom] = useState("");
  const [periodTo, setPeriodTo] = useState("");

  useEffect(() => {
    api<TimesheetRow[]>("/timesheets")
      .then(setRows)
      .catch((e) => setErr(String(e)));
  }, []);

  const totalAllTime = useMemo(() => rows.reduce((s, x) => s + (x.gross_pay || 0), 0), [rows]);

  const periodFilterActive = Boolean(periodFrom || periodTo);

  const displayRows = useMemo(() => {
    if (!periodFrom && !periodTo) return rows;
    return rows.filter((x) => {
      const ymd = timesheetRowYmd(x);
      if (!ymd) return false;
      if (periodFrom && ymd < periodFrom) return false;
      if (periodTo && ymd > periodTo) return false;
      return true;
    });
  }, [rows, periodFrom, periodTo]);

  const periodTotal = useMemo(() => displayRows.reduce((s, x) => s + (x.gross_pay || 0), 0), [displayRows]);

  const sortedDisplay = useMemo(
    () =>
      [...displayRows].sort((a, b) => {
        const da = timesheetRowYmd(a) || "";
        const db = timesheetRowYmd(b) || "";
        return db.localeCompare(da);
      }),
    [displayRows],
  );

  function presetThisMonth() {
    const now = new Date();
    setPeriodFrom(localDateYmd(new Date(now.getFullYear(), now.getMonth(), 1)));
    setPeriodTo(localDateYmd(now));
  }

  function presetLast30Days() {
    const now = new Date();
    const start = new Date(now);
    start.setDate(start.getDate() - 30);
    setPeriodFrom(localDateYmd(start));
    setPeriodTo(localDateYmd(now));
  }

  function clearPeriod() {
    setPeriodFrom("");
    setPeriodTo("");
  }

  const shiftDayLabel = (x: TimesheetRow) => {
    const ymd = timesheetRowYmd(x);
    if (!ymd) return "—";
    try {
      return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(`${ymd}T12:00:00`));
    } catch {
      return ymd;
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 md:px-8">
      <PageHeader
        eyebrow={t("worker_earnings_eyebrow")}
        title={t("worker_earnings_title")}
        description={t("worker_earnings_description")}
      />
      {err && <p className="mb-6 text-sm text-error">{err}</p>}

      <div className="mb-8 grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-outline-variant/15 bg-surface-container-lowest p-6 shadow-sm">
          <p className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">{t("worker_earnings_total_all_time")}</p>
          <p className="mt-2 font-headline text-3xl font-extrabold tracking-tight text-on-surface">{fmtMoney(totalAllTime)}</p>
        </div>
        {periodFilterActive ? (
          <div className="rounded-2xl border border-primary/25 bg-primary-container/15 p-6 shadow-sm">
            <p className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">{t("worker_earnings_period_total")}</p>
            <p className="mt-2 font-headline text-3xl font-extrabold tracking-tight text-primary">{fmtMoney(periodTotal)}</p>
            <p className="mt-2 text-xs text-on-surface-variant">
              {periodFrom || "…"} — {periodTo || "…"}
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-outline-variant/30 bg-surface-container-low/40 p-6">
            <p className="text-sm font-medium text-on-surface">{t("worker_earnings_period_hint_title")}</p>
            <p className="mt-1 text-xs text-on-surface-variant">{t("worker_earnings_period_hint_body")}</p>
          </div>
        )}
      </div>

      <section className="mb-10 rounded-2xl border border-outline-variant/15 bg-surface-container-lowest p-5 md:p-6">
        <h2 className="font-headline text-sm font-bold text-on-surface">{t("worker_earnings_filter_heading")}</h2>
        <div className="mt-4 flex flex-col gap-4 md:flex-row md:flex-wrap md:items-end">
          <div>
            <label className="mb-1 block text-xs font-medium text-on-surface-variant" htmlFor="earnings-from">
              {t("worker_earnings_filter_from")}
            </label>
            <input
              id="earnings-from"
              type="date"
              className="rounded-xl border border-outline-variant/30 bg-surface-container-low px-3 py-2 text-sm text-on-surface"
              value={periodFrom}
              onChange={(e) => setPeriodFrom(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-on-surface-variant" htmlFor="earnings-to">
              {t("worker_earnings_filter_to")}
            </label>
            <input
              id="earnings-to"
              type="date"
              className="rounded-xl border border-outline-variant/30 bg-surface-container-low px-3 py-2 text-sm text-on-surface"
              value={periodTo}
              onChange={(e) => setPeriodTo(e.target.value)}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-xl border border-outline-variant/30 bg-surface-container-high px-3 py-2 text-xs font-semibold text-on-surface hover:bg-surface-variant"
              onClick={presetThisMonth}
            >
              {t("worker_earnings_preset_this_month")}
            </button>
            <button
              type="button"
              className="rounded-xl border border-outline-variant/30 bg-surface-container-high px-3 py-2 text-xs font-semibold text-on-surface hover:bg-surface-variant"
              onClick={presetLast30Days}
            >
              {t("worker_earnings_preset_last_30")}
            </button>
            <button
              type="button"
              className="rounded-xl border border-outline-variant/30 px-3 py-2 text-xs font-semibold text-on-surface-variant hover:bg-surface-container-high"
              onClick={clearPeriod}
            >
              {t("worker_earnings_clear_period")}
            </button>
          </div>
        </div>
      </section>

      <ul className="space-y-3">
        {sortedDisplay.map((x) => (
          <li
            key={x.id}
            className="flex flex-col gap-2 rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-5 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              {x.job_title ? <p className="font-semibold text-on-surface">{x.job_title}</p> : null}
              <p className="text-xs text-on-surface-variant">
                {t("worker_earnings_shift_day")}: {shiftDayLabel(x)}
              </p>
              <span className="mt-1 inline-block font-mono text-sm text-on-surface-variant">#{x.id}</span>
              {(x.clock_in_at || x.clock_out_at) && (
                <p className="mt-1 text-xs text-on-surface-variant">
                  {x.clock_in_at && (
                    <span>
                      {t("worker_earnings_clock_in_short")}{" "}
                      {new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(x.clock_in_at))}
                    </span>
                  )}
                  {x.clock_in_at && x.clock_out_at ? " · " : ""}
                  {x.clock_out_at && (
                    <span>
                      {t("worker_earnings_clock_out_short")}{" "}
                      {new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(x.clock_out_at))}
                    </span>
                  )}
                </p>
              )}
            </div>
            <span className="font-headline text-lg font-bold">{fmtMoney(x.gross_pay)}</span>
            <span className="rounded-full bg-secondary-container px-3 py-1 text-sm font-medium text-on-secondary-container w-fit">
              {x.status}
            </span>
          </li>
        ))}
      </ul>
      {rows.length === 0 && !err && <p className="text-on-surface-variant">{t("worker_earnings_empty_all")}</p>}
      {rows.length > 0 && sortedDisplay.length === 0 && !err && (
        <p className="text-on-surface-variant">{t("worker_earnings_empty_period")}</p>
      )}
    </div>
  );
}

type ClockAssignment = {
  assignment_id: number;
  shift_id: number;
  job_title: string;
  job_site_lat: number;
  job_site_lng: number;
  geofence_radius_m: number;
  starts_at: string;
  ends_at: string;
  clock_in_allowed_not_before: string;
  clock_in_grace_ends_at: string;
  already_clocked_in: boolean;
  already_clocked_out: boolean;
  is_late_window: boolean;
  can_clock_in_now: boolean;
};

const QR_READER_ELEMENT_ID = "worker-qr-reader";

type ClockOutPaySummary = {
  gross_pay: number;
  total_hours: number;
  scheduled_hours: number;
  pay_pending_review: boolean;
  timesheet_created: boolean;
};

function clockAssignmentIdFromSearch(search: string): number {
  const sp = new URLSearchParams(search);
  const raw = sp.get("assignment") ?? sp.get("assignment_id");
  if (!raw?.trim()) return NaN;
  const n = Number.parseInt(raw.trim(), 10);
  return Number.isFinite(n) && n > 0 ? n : NaN;
}

function ClockPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const parsedAssignment = useMemo(() => clockAssignmentIdFromSearch(location.search), [location.search]);

  const [ctx, setCtx] = useState<{ assignment: ClockAssignment | null } | null>(null);
  const [ctxErr, setCtxErr] = useState<string | null>(null);
  const [, setTick] = useState(0);
  const [lat, setLat] = useState<number | null>(null);
  const [lng, setLng] = useState<number | null>(null);
  const [geoErr, setGeoErr] = useState<string | null>(null);
  const [geoLoading, setGeoLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [msgKind, setMsgKind] = useState<ClockNoticeKind>("info");
  const [busy, setBusy] = useState(false);
  const [pasteToken, setPasteToken] = useState("");
  const [scanning, setScanning] = useState(false);
  const [lastPaySummary, setLastPaySummary] = useState<ClockOutPaySummary | null>(null);
  const scannerRef = useRef<Html5Qrcode | null>(null);

  const loadContext = useCallback(() => {
    const q =
      Number.isFinite(parsedAssignment) && parsedAssignment > 0
        ? `?assignment_id=${parsedAssignment}`
        : "";
    setCtxErr(null);
    api<{ assignment: ClockAssignment | null }>(`/worker/clock/context${q}`)
      .then(setCtx)
      .catch((e) => setCtxErr(String(e)));
  }, [parsedAssignment]);

  useEffect(() => {
    loadContext();
  }, [loadContext]);

  useEffect(() => {
    const iv = window.setInterval(() => setTick((x) => x + 1), 1000);
    return () => window.clearInterval(iv);
  }, []);

  useEffect(() => {
    setGeoLoading(true);
    setGeoErr(null);
    if (!navigator.geolocation) {
      setGeoErr(t("map_geo_unavailable"));
      setGeoLoading(false);
      return;
    }
    let watchId: number | null = null;
    try {
      watchId = navigator.geolocation.watchPosition(
        (pos) => {
          setLat(pos.coords.latitude);
          setLng(pos.coords.longitude);
          setGeoLoading(false);
          setGeoErr(null);
        },
        (err) => {
          setGeoLoading(false);
          if (err.code === 1) setGeoErr(t("map_geo_denied"));
          else setGeoErr(t("map_geo_error"));
        },
        { enableHighAccuracy: true, timeout: 25_000, maximumAge: 10_000 },
      );
    } catch {
      // Some browsers throw synchronously when geolocation is unavailable (e.g. insecure context).
      setGeoLoading(false);
      setGeoErr(t("map_geo_error"));
    }
    return () => {
      if (watchId != null) navigator.geolocation.clearWatch(watchId);
    };
  }, [t]);

  const a = ctx?.assignment ?? null;
  const now = Date.now();
  const openMs = a ? new Date(a.clock_in_allowed_not_before).getTime() : 0;
  const endMs = a ? new Date(a.ends_at).getTime() : 0;
  const canClockIn = !!a && !a.already_clocked_in && !a.already_clocked_out && a.can_clock_in_now;
  const showLateWarning = !!a && !a.already_clocked_in && a.is_late_window && a.can_clock_in_now;
  const canScan =
    !!a &&
    !a.already_clocked_out &&
    (a.already_clocked_in || a.can_clock_in_now) &&
    lat != null &&
    lng != null &&
    !busy;

  const stopScanner = useCallback(async () => {
    if (scannerRef.current) {
      try {
        await scannerRef.current.stop();
      } catch {
        /* ignore */
      }
      try {
        scannerRef.current.clear();
      } catch {
        /* ignore */
      }
      scannerRef.current = null;
    }
    setScanning(false);
  }, []);

  useEffect(() => {
    return () => {
      void stopScanner();
    };
  }, [stopScanner]);

  async function startCameraScan() {
    setMsg(null);
    setMsgKind("info");
    setLastPaySummary(null);
    if (!canScan) {
      if (!a) {
        setMsg(t("clock_page_no_shift"));
        setMsgKind("warning");
      } else if (lat == null) {
        setMsg(t("clock_page_gps_required"));
        setMsgKind("warning");
      }
      return;
    }
    await stopScanner();
    setScanning(true);
    await new Promise((r) => requestAnimationFrame(r));
    const h = new Html5Qrcode(QR_READER_ELEMENT_ID);
    scannerRef.current = h;
    try {
      await h.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        async (decodedText) => {
          await stopScanner();
          await submitQrToken(decodedText);
        },
        () => {},
      );
    } catch (e) {
      scannerRef.current = null;
      setScanning(false);
      setMsg(`${t("clock_page_scanner_error")}: ${String(e)}`);
      setMsgKind("error");
    }
  }

  async function submitQrToken(raw: string) {
    const token = raw.trim();
    setMsg(null);
    setMsgKind("info");
    setLastPaySummary(null);
    if (!a) {
      setMsg(t("clock_page_no_shift"));
      setMsgKind("warning");
      return;
    }
    if (!token) {
      setMsg(t("clock_page_paste_empty"));
      setMsgKind("warning");
      return;
    }
    if (lat == null || lng == null) {
      setMsg(t("clock_page_gps_required"));
      setMsgKind("warning");
      return;
    }
    setBusy(true);
    const auth = getToken();
    try {
      const res = await fetch(apiUrl("/attendance/qr-clock"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(auth ? { Authorization: `Bearer ${auth}` } : {}),
        },
        body: JSON.stringify({ token, lat, lng }),
      });
      const text = await res.text();
      let body: Record<string, unknown> | null = null;
      try {
        body = JSON.parse(text) as Record<string, unknown>;
      } catch {
        body = null;
      }
      if (!res.ok) {
        const parsed = parseQrClockApiError(body, text, res.statusText, t);
        setMsg(parsed.text);
        setMsgKind(parsed.kind);
        setPasteToken("");
        return;
      }
      if (body && typeof body.gross_pay === "number") {
        setLastPaySummary({
          gross_pay: body.gross_pay,
          total_hours: typeof body.total_hours === "number" ? body.total_hours : 0,
          scheduled_hours: typeof body.scheduled_hours === "number" ? body.scheduled_hours : 0,
          pay_pending_review: Boolean(body.pay_pending_review),
          timesheet_created: Boolean(body.timesheet_created),
        });
        setMsg(t("clock_page_clock_out_ok"));
        setMsgKind("success");
      } else if (body?.ok) {
        setMsg(t("clock_page_clock_in_ok"));
        setMsgKind("success");
      } else {
        setMsg(text);
        setMsgKind("info");
      }
      setPasteToken("");
      loadContext();
    } catch (e) {
      setMsg(String(e));
      setMsgKind("error");
    } finally {
      setBusy(false);
    }
  }

  const openTimeLabel = a
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
        new Date(a.clock_in_allowed_not_before),
      )
    : "";

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 md:px-8">
      <PageHeader
        eyebrow="Attendance"
        title={t("clock_page_title")}
        description={t("clock_page_description_qr")}
      />
      {ctxErr && <p className="mb-4 text-sm text-error">{ctxErr}</p>}
      <div className="space-y-4 rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-8 shadow-sm">
        {!a && !ctxErr && ctx && <p className="text-on-surface-variant">{t("clock_page_no_shift")}</p>}
        {a && (
          <div className="space-y-2 border-b border-outline-variant/10 pb-4">
            <p className="font-headline text-xl font-bold text-on-surface">{a.job_title}</p>
            <p className="text-sm text-on-surface-variant">
              {t("clock_page_shift_label")} #{a.shift_id} · {t("clock_page_assignment_label")} #{a.assignment_id}
            </p>
            <p className="text-sm text-on-surface-variant">
              {fmtDate(a.starts_at)} · {fmtTime(a.starts_at)} – {fmtTime(a.ends_at)}
            </p>
            {a.already_clocked_in && !a.already_clocked_out && (
              <p className="text-sm font-semibold text-primary">{t("clock_page_scan_out_hint")}</p>
            )}
            {a.already_clocked_out && <p className="text-sm font-semibold text-on-surface-variant">Shift completed.</p>}
            {!a.already_clocked_in && !canClockIn && now < openMs && (
              <p className="text-sm text-amber-800 dark:text-amber-200">
                {t("clock_page_available_at", { time: openTimeLabel })}
              </p>
            )}
            {!a.already_clocked_in && !canClockIn && now >= openMs && now < endMs && (
              <p className="text-sm text-error">{t("clock_page_grace_expired")}</p>
            )}
            {showLateWarning && <p className="text-sm text-error">{t("clock_page_late_warning")}</p>}
            {Number.isFinite(a.job_site_lat) && Number.isFinite(a.job_site_lng) && (
              <ClockSiteMap
                key={a.assignment_id}
                jobSiteLat={a.job_site_lat}
                jobSiteLng={a.job_site_lng}
                geofenceRadiusM={
                  typeof a.geofence_radius_m === "number" && a.geofence_radius_m > 0 ? a.geofence_radius_m : 200
                }
                youLat={lat}
                youLng={lng}
                height="260px"
                className="pt-2"
              />
            )}
          </div>
        )}
        <p className="text-xs text-on-surface-variant">
          {geoLoading
            ? t("clock_page_gps_loading")
            : lat != null && lng != null
              ? t("clock_page_gps_ready")
              : geoErr || ""}
        </p>
        {geoErr && <p className="text-sm text-error">{geoErr}</p>}
        <div className="space-y-4 rounded-xl border border-outline-variant/10 bg-surface-container-low p-4">
          <p className="text-sm font-semibold text-on-surface">{t("clock_page_scan_title")}</p>
          <p className="text-xs text-on-surface-variant">{t("clock_page_scan_help")}</p>
          <div
            id={QR_READER_ELEMENT_ID}
            className={`mx-auto w-full max-w-sm overflow-hidden rounded-xl bg-black/80 ${scanning ? "min-h-[240px]" : "min-h-0"}`}
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!canScan || scanning}
              className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-on-primary disabled:opacity-50"
              onClick={() => void startCameraScan()}
            >
              {t("clock_page_scan_camera")}
            </button>
            <button
              type="button"
              disabled={!scanning}
              className="rounded-xl border border-outline-variant/40 px-4 py-2.5 text-sm font-semibold text-on-surface disabled:opacity-50"
              onClick={() => void stopScanner()}
            >
              {t("clock_page_scan_stop")}
            </button>
          </div>
          <div className="border-t border-outline-variant/15 pt-4">
            <label className="block text-xs font-semibold text-on-surface-variant">{t("clock_page_paste_label")}</label>
            <textarea
              value={pasteToken}
              onChange={(e) => setPasteToken(e.target.value)}
              rows={3}
              disabled={!a || a.already_clocked_out || busy}
              placeholder={t("clock_page_paste_placeholder")}
              className="mt-2 w-full rounded-xl border border-outline-variant/30 bg-surface-container-lowest px-3 py-2 text-xs text-on-surface"
            />
            <button
              type="button"
              disabled={!canScan || !pasteToken.trim()}
              className="mt-2 rounded-xl bg-secondary-container px-4 py-2 text-sm font-semibold text-on-secondary-container disabled:opacity-50"
              onClick={() => void submitQrToken(pasteToken)}
            >
              {t("clock_page_paste_submit")}
            </button>
          </div>
        </div>
        {lastPaySummary && (
          <div className="rounded-xl border border-primary/30 bg-primary-container/20 p-4 text-on-surface">
            <p className="font-headline text-lg font-bold">{t("clock_page_pay_summary_title")}</p>
            <p className="mt-2 text-sm">
              {t("clock_page_pay_hours", { hours: lastPaySummary.total_hours.toFixed(2) })} ·{" "}
              {t("clock_page_pay_scheduled", { hours: lastPaySummary.scheduled_hours.toFixed(2) })}
            </p>
            <p className="mt-1 text-xl font-bold text-primary">{fmtMoney(lastPaySummary.gross_pay)}</p>
            {lastPaySummary.pay_pending_review && (
              <p className="mt-2 text-xs text-amber-800 dark:text-amber-200">{t("clock_page_pay_pending_review")}</p>
            )}
          </div>
        )}
        {msg && (
          <p
            role="alert"
            className={`whitespace-pre-wrap text-sm font-medium ${
              msgKind === "error"
                ? "text-error"
                : msgKind === "warning"
                  ? "text-amber-800 dark:text-amber-200"
                  : msgKind === "success"
                    ? "text-primary"
                    : "text-on-surface"
            }`}
          >
            {msg}
          </p>
        )}
      </div>
    </div>
  );
}

type ProfileCompletenessItem = { id: string; done: boolean; required_for_compliance: boolean };
type ProfileCompletenessPayload = { profile_completeness_pct: number; items: ProfileCompletenessItem[] };

type WorkerProfileSnapshot = {
  full_name: string;
  phone: string;
  email: string | null;
  languages: string[];
  job_type_preferences: string[];
  skills: string[];
  certifications: string[];
  availability: Record<string, unknown>;
  location_lat: number | null;
  location_lng: number | null;
  bank_name: string | null;
  work_pass_not_applicable: boolean;
  profile_completeness_pct: number;
  pdpa_consent: boolean;
};

type WorkerReputation = {
  rating_avg: number;
  tier: string;
  ratings: Array<{
    stars: number;
    comment: string | null;
    created_at: string;
    client_org_id: number | null;
    client_org_name: string | null;
    job_title: string | null;
    shift_starts_at: string | null;
  }>;
  preferred_by_clients: Array<{ client_org_id: number; name: string }>;
};

const ACCOUNT_STEPS = 7;

function ProfileAccountTab() {
  const { t } = useTranslation();
  const [step, setStep] = useState(1);
  const [snapshot, setSnapshot] = useState<WorkerProfileSnapshot | null>(null);
  const [langsText, setLangsText] = useState("");
  const [mapLat, setMapLat] = useState(DEFAULT_MAP_CENTER.lat);
  const [mapLng, setMapLng] = useState(DEFAULT_MAP_CENTER.lng);
  const [pdpaAck, setPdpaAck] = useState(false);
  const [docs, setDocs] = useState<{ id: number; doc_type: string }[]>([]);
  const [completenessDetail, setCompletenessDetail] = useState<ProfileCompletenessPayload | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function refreshCompleteness() {
    try {
      const c = await api<ProfileCompletenessPayload>("/workers/me/profile/completeness");
      setCompletenessDetail(c);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    let cancelled = false;
    setLoadErr(null);
    api<WorkerProfileSnapshot>("/workers/me/profile")
      .then((p) => {
        if (cancelled) return;
        setSnapshot(p);
        setLangsText((p.languages || []).join(", "));
        if (p.location_lat != null && p.location_lng != null) {
          setMapLat(p.location_lat);
          setMapLng(p.location_lng);
        }
      })
      .catch((e) => {
        if (!cancelled) setLoadErr(String(e));
      });
    api<{ id: number; doc_type: string }[]>("/workers/me/documents").then(setDocs).catch(() => {});
    void refreshCompleteness();
    return () => {
      cancelled = true;
    };
  }, []);

  async function savePartial() {
    if (!snapshot) {
      setMsg(t("settings_location_load_first"));
      return;
    }
    setSaving(true);
    setMsg(null);
    try {
      await api("/workers/me/profile", {
        method: "PUT",
        json: {
          full_name: snapshot.full_name,
          phone: snapshot.phone,
          email: snapshot.email,
          languages: langsText
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          job_type_preferences: snapshot.job_type_preferences,
          skills: snapshot.skills,
          certifications: snapshot.certifications,
          availability: snapshot.availability && Object.keys(snapshot.availability).length ? snapshot.availability : { always: true },
          bank_name: snapshot.bank_name ?? undefined,
          work_pass_not_applicable: snapshot.work_pass_not_applicable,
          location_lat: mapLat,
          location_lng: mapLng,
        },
      });
      let p = await api<WorkerProfileSnapshot>("/workers/me/profile");
      setSnapshot(p);
      setLangsText((p.languages || []).join(", "));
      if (pdpaAck && !p.pdpa_consent) {
        await api("/workers/me/pdpa-consent", { method: "POST" });
        p = await api<WorkerProfileSnapshot>("/workers/me/profile");
        setSnapshot(p);
      }
      setMsg(t("settings_location_saved"));
      await refreshCompleteness();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setSaving(false);
    }
  }

  const inputClass =
    "w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-4 py-3 text-on-surface placeholder:text-on-surface-variant focus:ring-2 focus:ring-primary";

  if (loadErr) {
    return <p className="text-sm text-error">{loadErr}</p>;
  }
  if (!snapshot) {
    return <p className="text-on-surface-variant">{t("settings_loading")}</p>;
  }

  const profilePct = completenessDetail?.profile_completeness_pct ?? snapshot.profile_completeness_pct;
  const checklistItems = completenessDetail?.items ?? [];

  return (
    <div className="rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-8 shadow-sm">
      <div className="mb-2 flex items-center justify-between gap-2 text-xs text-on-surface-variant">
        <span>{t("onb_progress_label")}</span>
        <span className="font-mono text-primary">{profilePct}%</span>
      </div>
      <div className="mb-6 h-2 overflow-hidden rounded-full bg-surface-container-high">
        <div className="h-full bg-primary transition-all" style={{ width: `${profilePct}%` }} />
      </div>
      {checklistItems.length > 0 && (
        <div className="mb-8 rounded-xl border border-outline-variant/15 bg-surface-container-low/80 p-4">
          <p className="text-sm font-semibold text-on-surface mb-3">{t("completeness_checklist_title")}</p>
          <ul className="space-y-2 max-h-56 overflow-y-auto pr-1">
            {checklistItems.map((row) => {
              const labelKey = `completeness_item_${row.id}` as const;
              return (
                <li key={row.id} className="flex items-start gap-2 text-sm">
                  <span className={row.done ? "text-primary shrink-0" : "text-on-surface-variant shrink-0"} aria-hidden>
                    {row.done ? "✓" : "○"}
                  </span>
                  <span className={row.done ? "text-on-surface-variant line-through" : "text-on-surface"}>
                    {t(labelKey)}
                    <span className="ml-1 text-[10px] uppercase tracking-wide text-on-surface-variant">
                      {row.required_for_compliance ? `· ${t("completeness_required")}` : `· ${t("completeness_optional")}`}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <p className="mb-6 text-sm text-on-surface-variant">{t("step_x_of_y", { current: step, total: ACCOUNT_STEPS })}</p>

      {step === 1 && (
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm text-on-surface-variant">{t("wizard_name")}</label>
            <input
              className={`${inputClass} text-lg`}
              value={snapshot.full_name}
              onChange={(e) => setSnapshot((s) => (s ? { ...s, full_name: e.target.value } : s))}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-on-surface-variant">{t("worker_profile_phone")}</label>
            <input
              className={inputClass}
              value={snapshot.phone}
              onChange={(e) => setSnapshot((s) => (s ? { ...s, phone: e.target.value } : s))}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-on-surface-variant">{t("worker_profile_email")}</label>
            <input
              className={inputClass}
              type="email"
              value={snapshot.email ?? ""}
              onChange={(e) => setSnapshot((s) => (s ? { ...s, email: e.target.value || null } : s))}
            />
          </div>
        </div>
      )}
      {step === 2 && (
        <div className="space-y-2">
          <label className="text-sm text-on-surface-variant">{t("wizard_languages")}</label>
          <input className={inputClass} value={langsText} onChange={(e) => setLangsText(e.target.value)} />
        </div>
      )}
      {step === 3 && (
        <div className="space-y-2">
          <label className="text-sm text-on-surface-variant">{t("wizard_job_types")}</label>
          <JobTypeMultiPicker
            t={t}
            selected={(snapshot.job_type_preferences || []).filter(isAllowedJobType)}
            onChange={(job_type_preferences) => setSnapshot((s) => (s ? { ...s, job_type_preferences } : s))}
            selectClassName={`${inputClass} flex-1 min-w-0`}
            addButtonClassName="rounded-xl border border-outline-variant/30 bg-surface-container-high px-4 py-3 font-medium text-on-surface shrink-0"
            chipButtonClassName="text-xs bg-surface-container-high px-2 py-1 rounded-lg text-on-surface"
          />
        </div>
      )}
      {step === 4 && (
        <div className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm text-on-surface-variant">{t("wizard_skills")}</label>
            <SkillMultiPicker
              t={t}
              selected={snapshot.skills}
              onChange={(skills) => setSnapshot((s) => (s ? { ...s, skills } : s))}
              inputClassName={inputClass}
              addButtonClassName="rounded-xl border border-outline-variant/30 bg-surface-container-high px-4 py-3 font-medium text-on-surface shrink-0"
              chipButtonClassName="text-xs bg-surface-container-high px-2 py-1 rounded-lg text-on-surface"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm text-on-surface-variant">{t("wizard_certifications")}</label>
            <CertificationMultiPicker
              t={t}
              selected={snapshot.certifications}
              onChange={(certifications) => setSnapshot((s) => (s ? { ...s, certifications } : s))}
              inputClassName={inputClass}
              addButtonClassName="rounded-xl border border-outline-variant/30 bg-surface-container-high px-4 py-3 font-medium text-on-surface shrink-0"
              chipButtonClassName="text-xs bg-surface-container-high px-2 py-1 rounded-lg text-on-surface"
            />
          </div>
        </div>
      )}
      {step === 5 && (
        <div className="space-y-2">
          <label className="text-sm text-on-surface-variant">{t("wizard_location")}</label>
          <p className="text-xs text-on-surface-variant">{t("settings_location_gps_hint")}</p>
          <LocationMapPicker
            latitude={mapLat}
            longitude={mapLng}
            onChange={({ lat, lng }) => {
              setMapLat(lat);
              setMapLng(lng);
            }}
            lightMode
            height="280px"
            showGeolocationButton
          />
        </div>
      )}
      {step === 6 && (
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm text-on-surface-variant">{t("worker_profile_bank_name")}</label>
            <input
              className={inputClass}
              value={snapshot.bank_name ?? ""}
              onChange={(e) => setSnapshot((s) => (s ? { ...s, bank_name: e.target.value || null } : s))}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-on-surface">
            <input
              type="checkbox"
              checked={snapshot.work_pass_not_applicable}
              onChange={(e) => setSnapshot((s) => (s ? { ...s, work_pass_not_applicable: e.target.checked } : s))}
              className="rounded border-outline-variant"
            />
            {t("worker_profile_work_pass_na")}
          </label>
        </div>
      )}
      {step === 7 && (
        <div className="space-y-3">
          {snapshot.pdpa_consent ? (
            <p className="text-sm text-on-surface-variant">{t("wizard_pdpa")} — saved.</p>
          ) : (
            <label className="flex items-center gap-2 text-sm text-on-surface">
              <input type="checkbox" checked={pdpaAck} onChange={(e) => setPdpaAck(e.target.checked)} className="rounded border-outline-variant" />
              {t("wizard_pdpa")}
            </label>
          )}
          <p className="text-xs text-on-surface-variant">
            Documents: upload via API `/workers/me/documents` or future UI. Listed: {docs.length}
          </p>
        </div>
      )}

      <div className="mt-8 flex flex-wrap gap-2">
        {step > 1 && (
          <button type="button" className="rounded-xl bg-surface-container-high px-4 py-2 font-medium text-on-surface" onClick={() => setStep((s) => s - 1)}>
            {t("wizard_back")}
          </button>
        )}
        {step < ACCOUNT_STEPS && (
          <button type="button" className="rounded-xl bg-primary px-4 py-2 font-medium text-on-primary" onClick={() => setStep((s) => s + 1)}>
            {t("wizard_next")}
          </button>
        )}
        <button
          type="button"
          disabled={saving}
          className="rounded-xl bg-secondary-container px-4 py-2 font-medium text-on-secondary-container disabled:opacity-50"
          onClick={() => void savePartial()}
        >
          {saving ? "…" : t("wizard_save")}
        </button>
      </div>
      {msg && <p className="mt-4 text-sm text-primary">{msg}</p>}
    </div>
  );
}

function ReputationTab() {
  const { t } = useTranslation();
  const [data, setData] = useState<WorkerReputation | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<WorkerReputation>("/workers/me/reputation")
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (err) return <p className="text-sm text-error">{err}</p>;
  if (!data) return <p className="text-on-surface-variant">{t("settings_loading")}</p>;

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-6 shadow-sm">
        <dl className="flex flex-wrap gap-6">
          <div>
            <dt className="text-xs font-medium text-on-surface-variant">{t("worker_profile_rating_avg")}</dt>
            <dd className="text-2xl font-bold text-on-surface">{data.rating_avg.toFixed(1)} / 5</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-on-surface-variant">{t("worker_profile_tier")}</dt>
            <dd className="text-lg font-semibold capitalize text-on-surface">{data.tier}</dd>
          </div>
        </dl>
      </div>
      <div className="rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold text-on-surface">{t("worker_profile_recent_ratings")}</h2>
        {data.ratings.length === 0 ? (
          <p className="text-sm text-on-surface-variant">{t("worker_profile_no_ratings")}</p>
        ) : (
          <ul className="space-y-4">
            {data.ratings.map((r, i) => (
              <li key={`${r.created_at}-${i}`} className="border-b border-outline-variant/10 pb-4 last:border-0 last:pb-0">
                <p className="font-medium text-on-surface">
                  {"★".repeat(r.stars)}
                  {"☆".repeat(5 - r.stars)}
                </p>
                <p className="text-sm text-on-surface-variant">
                  {r.client_org_name ?? "—"}
                  {r.job_title ? ` · ${r.job_title}` : ""}
                  {r.shift_starts_at ? ` · ${fmtDate(r.shift_starts_at)}` : ""}
                </p>
                <p className="text-xs text-on-surface-variant">{fmtDate(r.created_at)}</p>
                {r.comment ? <p className="mt-1 text-sm text-on-surface">{r.comment}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold text-on-surface">{t("worker_profile_preferred_by")}</h2>
        {data.preferred_by_clients.length === 0 ? (
          <p className="text-sm text-on-surface-variant">{t("worker_profile_no_preferred")}</p>
        ) : (
          <ul className="list-inside list-disc space-y-1 text-sm text-on-surface">
            {data.preferred_by_clients.map((c) => (
              <li key={c.client_org_id}>{c.name}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function WorkerProfilePage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get("tab") === "reputation" ? "reputation" : "account";

  function goTab(next: "account" | "reputation") {
    if (next === "account") {
      setSearchParams({}, { replace: true });
    } else {
      setSearchParams({ tab: "reputation" }, { replace: true });
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 md:px-8">
      <PageHeader
        eyebrow="Account"
        title={t("profile")}
        description={tab === "reputation" ? t("worker_profile_reputation_intro") : undefined}
      />
      <div className="mb-8 flex flex-wrap items-center gap-1 overflow-x-auto rounded-2xl bg-surface-container p-1">
        <button
          type="button"
          onClick={() => goTab("account")}
          className={[
            "rounded-xl px-6 py-2.5 text-sm font-bold whitespace-nowrap transition-colors",
            tab === "account" ? "bg-surface-container-lowest text-primary shadow-sm" : "font-medium text-on-surface-variant hover:text-on-surface",
          ].join(" ")}
        >
          {t("worker_profile_tab_account")}
        </button>
        <button
          type="button"
          onClick={() => goTab("reputation")}
          className={[
            "rounded-xl px-6 py-2.5 text-sm font-bold whitespace-nowrap transition-colors",
            tab === "reputation" ? "bg-surface-container-lowest text-primary shadow-sm" : "font-medium text-on-surface-variant hover:text-on-surface",
          ].join(" ")}
        >
          {t("worker_profile_tab_reputation")}
        </button>
      </div>
      {tab === "account" ? <ProfileAccountTab /> : <ReputationTab />}
    </div>
  );
}

export default function WorkerApp() {
  return (
    <Routes>
      <Route path="onboarding" element={<WorkerOnboardingPage />} />
      <Route
        element={
          <WorkerPortalLayout>
            <Outlet />
          </WorkerPortalLayout>
        }
      >
        <Route index element={<OffersHome />} />
        <Route path="marketplace" element={<MarketplacePage />} />
        <Route path="marketplace/:shiftId" element={<MarketplaceShiftDetailPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="shifts" element={<ShiftsPage />} />
        <Route path="profile" element={<WorkerProfilePage />} />
        <Route path="settings" element={<Navigate to="/worker/profile?tab=account" replace />} />
        <Route path="earnings" element={<EarningsPage />} />
        <Route path="clock" element={<ClockPage />} />
      </Route>
    </Routes>
  );
}
