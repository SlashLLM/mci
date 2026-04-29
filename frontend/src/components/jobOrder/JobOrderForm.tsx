import { useEffect, useId, useState } from "react";
import type { TFunction } from "i18next";
import { api } from "../../api";
import { isAllowedJobType, JOB_TYPES } from "../../constants/jobTypes";
import { DEFAULT_MAP_CENTER, LocationMapPicker } from "../maps/LocationMapPicker";
import { CertificationMultiPicker } from "../certifications/CertificationMultiPicker";
import { SkillMultiPicker } from "../skills/SkillMultiPicker";
import { DEFAULT_MATCH_WEIGHTS, MatchWeightFields, type MatchWeightConfig } from "./MatchWeightFields";

export type ShiftRow = {
  starts_local: string;
  ends_local: string;
  workers_required: number;
};

type AutomaticDispatchMode = "fcfs" | "performance_priority" | "preferred_priority";

function toDatetimeLocalValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function defaultShiftRow(): ShiftRow {
  const start = new Date();
  start.setMinutes(0, 0, 0);
  start.setHours(9);
  const end = new Date(start);
  end.setHours(17);
  return { starts_local: toDatetimeLocalValue(start), ends_local: toDatetimeLocalValue(end), workers_required: 1 };
}

type Props = {
  t: TFunction;
  mode: "client" | "ta";
  organizations?: { id: number; name: string }[];
  onSuccess: () => void;
  /** Light surfaces for client portal (vs TA dark dashboard). */
  lightMode?: boolean;
};

export function JobOrderForm({ t, mode, organizations = [], onSuccess, lightMode = false }: Props) {
  const inputClass = lightMode
    ? "w-full bg-surface-container-lowest border border-outline-variant/40 rounded-xl px-3 py-2 text-sm text-on-background"
    : "w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm";
  const labelClass = lightMode ? "block text-xs text-on-surface-variant mb-1" : "block text-xs text-slate-500 mb-1";
  const chipBtn = lightMode ? "px-3 bg-surface-container-high rounded-lg text-sm text-on-surface shrink-0" : "px-3 bg-slate-800 rounded-lg text-sm shrink-0";
  const chipTag = lightMode ? "text-xs bg-primary-container/60 text-on-primary-container px-2 py-1 rounded-lg" : "text-xs bg-slate-800 px-2 py-1 rounded-lg";
  const sectionBox = lightMode ? "border border-outline-variant/30 rounded-xl p-4 space-y-3" : "border border-slate-800 rounded-xl p-4 space-y-3";
  const sectionTitle = lightMode ? "text-sm font-medium text-on-surface" : "text-sm font-medium text-slate-200";
  const hint = lightMode ? "text-xs text-on-surface-variant" : "text-xs text-slate-500";
  const rowBorder = lightMode ? "border-b border-outline-variant/25 pb-3" : "border-b border-slate-800/80 pb-3";
  const linkish = lightMode ? "text-xs text-primary px-2 py-1" : "text-xs text-sky-400 px-2 py-1";
  const dangerLink = lightMode ? "text-xs text-rose-600 px-2 py-1" : "text-xs text-rose-400 px-2 py-1";
  const rangeBar = lightMode ? "pt-4 border-t border-outline-variant/25 space-y-2" : "pt-4 border-t border-slate-800 space-y-2";
  const rangeMuted = lightMode ? "text-xs font-medium text-on-surface-variant" : "text-xs font-medium text-slate-400";
  const applyRangeBtn = lightMode ? "bg-surface-container-high text-on-surface px-3 py-2 rounded-lg text-sm" : "bg-slate-800 px-3 py-2 rounded-lg text-sm";
  const detailsBox = lightMode ? "text-sm border border-outline-variant/30 rounded-xl p-3" : "text-sm border border-slate-800 rounded-xl p-3";
  const summaryText = lightMode ? "cursor-pointer text-on-surface-variant" : "cursor-pointer text-slate-400";
  const addShiftText = lightMode ? "text-sm text-primary" : "text-sm text-sky-400";
  const errText = lightMode ? "text-sm text-rose-600" : "text-sm text-rose-400";
  const submitBtn = lightMode
    ? "glass-cta text-white font-semibold px-6 py-3 rounded-xl disabled:opacity-50 shadow-md"
    : "bg-sky-600 text-slate-950 font-semibold px-6 py-3 rounded-xl disabled:opacity-50";
  const [orgId, setOrgId] = useState<number | "">("");

  useEffect(() => {
    if (mode !== "ta" || organizations.length === 0) return;
    setOrgId((prev) => (prev === "" ? organizations[0].id : prev));
  }, [mode, organizations]);
  const [title, setTitle] = useState("");
  const [jobType, setJobType] = useState("");
  const [locationAddress, setLocationAddress] = useState("");
  const [pickLat, setPickLat] = useState(DEFAULT_MAP_CENTER.lat);
  const [pickLng, setPickLng] = useState(DEFAULT_MAP_CENTER.lng);
  const [payModel, setPayModel] = useState<"hourly" | "per_shift">("hourly");
  const [hourlyRate, setHourlyRate] = useState("");
  const [perShiftRate, setPerShiftRate] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [certs, setCerts] = useState<string[]>([]);
  const [uniform, setUniform] = useState("");
  const [special, setSpecial] = useState("");
  const [geofence, setGeofence] = useState("200");
  const [acceptanceMins, setAcceptanceMins] = useState("120");
  const [shifts, setShifts] = useState<ShiftRow[]>([defaultShiftRow()]);
  const [rangeFrom, setRangeFrom] = useState("");
  const [rangeTo, setRangeTo] = useState("");
  const [rangeWorkers, setRangeWorkers] = useState("1");
  const [defaultMatchWeights, setDefaultMatchWeights] = useState<MatchWeightConfig>(DEFAULT_MATCH_WEIGHTS);
  const [customizeMatchWeights, setCustomizeMatchWeights] = useState(false);
  const [matchWeights, setMatchWeights] = useState<MatchWeightConfig>(DEFAULT_MATCH_WEIGHTS);
  const [automaticDispatchEnabled, setAutomaticDispatchEnabled] = useState(false);
  const [automaticDispatchMode, setAutomaticDispatchMode] = useState<AutomaticDispatchMode>("fcfs");
  /** Hours after posting before non-Elite workers see the job in marketplace (stored as minutes on server). */
  const [automaticDispatchEliteExclusiveHours, setAutomaticDispatchEliteExclusiveHours] = useState("2");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const jobTypeFieldBase = useId().replace(/:/g, "_");
  const jobTypeInputId = `mci-job-type-${jobTypeFieldBase}`;
  const jobTypeDatalistId = `mci-job-type-list-${jobTypeFieldBase}`;

  function addRangeShifts() {
    if (!rangeFrom || !rangeTo || shifts.length < 1) return;
    const template = shifts[0];
    const ts = new Date(template.starts_local);
    const te = new Date(template.ends_local);
    if (Number.isNaN(ts.getTime()) || Number.isNaN(te.getTime())) return;
    const from = new Date(rangeFrom + "T12:00:00");
    const to = new Date(rangeTo + "T12:00:00");
    if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime()) || from > to) return;
    const w = Math.max(1, parseInt(rangeWorkers, 10) || 1);
    const next: ShiftRow[] = [...shifts];
    const cur = new Date(from);
    while (cur <= to) {
      const y = cur.getFullYear();
      const m = cur.getMonth();
      const day = cur.getDate();
      const s = new Date(ts);
      s.setFullYear(y, m, day);
      const e = new Date(te);
      e.setFullYear(y, m, day);
      next.push({
        starts_local: toDatetimeLocalValue(s),
        ends_local: toDatetimeLocalValue(e),
        workers_required: w,
      });
      cur.setDate(cur.getDate() + 1);
    }
    setShifts(next);
  }

  useEffect(() => {
    const jt = jobType.trim();
    if (!isAllowedJobType(jt)) {
      setDefaultMatchWeights(DEFAULT_MATCH_WEIGHTS);
      if (!customizeMatchWeights) setMatchWeights(DEFAULT_MATCH_WEIGHTS);
      return;
    }
    let cancelled = false;
    api<MatchWeightConfig>(`/job-orders/match-weights/defaults?job_type=${encodeURIComponent(jt)}`)
      .then((weights) => {
        if (cancelled) return;
        setDefaultMatchWeights(weights);
        if (!customizeMatchWeights) setMatchWeights(weights);
      })
      .catch(() => {
        if (cancelled) return;
        setDefaultMatchWeights(DEFAULT_MATCH_WEIGHTS);
        if (!customizeMatchWeights) setMatchWeights(DEFAULT_MATCH_WEIGHTS);
      });
    return () => {
      cancelled = true;
    };
  }, [customizeMatchWeights, jobType]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (mode === "ta" && (orgId === "" || orgId == null)) {
      setError(t("job_form_select_client"));
      return;
    }
    const la = pickLat;
    const ln = pickLng;
    if (!Number.isFinite(la) || !Number.isFinite(ln)) {
      setError(t("job_form_invalid_coords"));
      return;
    }
    const workersTotal = shifts.reduce((a, s) => a + (Number.isFinite(s.workers_required) ? s.workers_required : 0), 0);
    const eliteHours = Math.max(0, Number.parseFloat(automaticDispatchEliteExclusiveHours) || 2);
    const priorityWindowMinutes = Math.max(1, Math.round(eliteHours * 60));
    const jt = jobType.trim();
    if (!jt) {
      setError(t("job_form_required_core"));
      return;
    }
    if (!isAllowedJobType(jt)) {
      setError(t("job_type_invalid"));
      return;
    }
    const payload = {
      title: title.trim(),
      job_type: jt,
      location_address: locationAddress.trim(),
      location_lat: la,
      location_lng: ln,
      workers_required_total: Math.max(1, workersTotal || 1),
      pay_model: payModel,
      hourly_rate: payModel === "hourly" && hourlyRate ? parseFloat(hourlyRate) : null,
      per_shift_rate: payModel === "per_shift" && perShiftRate ? parseFloat(perShiftRate) : null,
      required_skills: skills,
      required_certifications: certs,
      uniform_notes: uniform.trim() || null,
      special_instructions: special.trim() || null,
      geofence_radius_m: Math.max(0, parseInt(geofence, 10) || 200),
      acceptance_window_minutes: Math.max(1, parseInt(acceptanceMins, 10) || 120),
      match_weights: customizeMatchWeights ? matchWeights : null,
      automatic_dispatch_enabled: automaticDispatchEnabled,
      automatic_dispatch_mode: automaticDispatchMode,
      automatic_dispatch_min_score: null,
      automatic_dispatch_top_percent: null,
      automatic_dispatch_priority_window_minutes:
        automaticDispatchEnabled && automaticDispatchMode === "performance_priority" ? priorityWindowMinutes : null,
      shifts: shifts.map((s) => ({
        starts_at: new Date(s.starts_local).toISOString(),
        ends_at: new Date(s.ends_local).toISOString(),
        workers_required: Math.max(1, s.workers_required || 1),
      })),
    };
    if (!payload.title || !payload.job_type || !payload.location_address) {
      setError(t("job_form_required_core"));
      return;
    }
    setSubmitting(true);
    try {
      if (mode === "client") {
        await api("/job-orders", { method: "POST", json: payload });
      } else {
        await api(`/job-orders/for-client/${orgId as number}`, { method: "POST", json: payload });
      }
      onSuccess();
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className={lightMode ? "space-y-6 max-w-3xl text-on-background" : "space-y-6 max-w-3xl"}>
      {mode === "ta" && (
        <div>
          <label className={labelClass}>{t("job_form_client_org")}</label>
          <select
            className={inputClass}
            value={orgId === "" ? "" : String(orgId)}
            onChange={(e) => setOrgId(e.target.value ? parseInt(e.target.value, 10) : "")}
            required
          >
            <option value="">{t("job_form_select_client")}</option>
            {organizations.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className={labelClass}>{t("job_form_title")}</label>
          <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} required />
        </div>
        <div className="sm:col-span-2">
          <label className={labelClass} htmlFor={jobTypeInputId}>
            {t("job_form_job_type")}
          </label>
          <input
            id={jobTypeInputId}
            className={inputClass}
            list={jobTypeDatalistId}
            value={jobType}
            onChange={(e) => setJobType(e.target.value)}
            onBlur={() => {
              const v = jobType.trim();
              if (v && !isAllowedJobType(v)) setJobType("");
            }}
            placeholder={t("job_type_select_placeholder")}
            autoComplete="off"
            required
          />
          <datalist id={jobTypeDatalistId}>
            {JOB_TYPES.map((jt) => (
              <option key={jt} value={jt} />
            ))}
          </datalist>
          <p className={`${hint} mt-1`}>{t("job_type_datalist_hint")}</p>
        </div>
        <div className="sm:col-span-2">
          <label className={labelClass}>{t("job_form_location")}</label>
          <input className={inputClass} value={locationAddress} onChange={(e) => setLocationAddress(e.target.value)} required />
        </div>
        <div className="sm:col-span-2">
          <label className={labelClass}>{t("job_form_map_location")}</label>
          <LocationMapPicker
            latitude={pickLat}
            longitude={pickLng}
            onChange={({ lat, lng }) => {
              setPickLat(lat);
              setPickLng(lng);
            }}
            lightMode={lightMode}
            height="260px"
          />
        </div>
      </div>

      <div>
        <p className={labelClass}>{t("job_form_pay_model")}</p>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input type="radio" name="pay" checked={payModel === "hourly"} onChange={() => setPayModel("hourly")} />
            {t("job_form_hourly")}
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name="pay" checked={payModel === "per_shift"} onChange={() => setPayModel("per_shift")} />
            {t("job_form_per_shift")}
          </label>
        </div>
        {payModel === "hourly" && (
          <div className="mt-2">
            <label className={labelClass}>{t("job_form_hourly_rate")}</label>
            <input className={inputClass} type="number" step="0.01" min="0" value={hourlyRate} onChange={(e) => setHourlyRate(e.target.value)} />
          </div>
        )}
        {payModel === "per_shift" && (
          <div className="mt-2">
            <label className={labelClass}>{t("job_form_per_shift_rate")}</label>
            <input className={inputClass} type="number" step="0.01" min="0" value={perShiftRate} onChange={(e) => setPerShiftRate(e.target.value)} />
          </div>
        )}
      </div>

      <div>
        <label className={labelClass}>{t("job_form_skills")}</label>
        <SkillMultiPicker
          t={t}
          selected={skills}
          onChange={setSkills}
          inputClassName={inputClass}
          addButtonClassName={chipBtn}
          chipButtonClassName={chipTag}
        />
      </div>

      <div>
        <label className={labelClass}>{t("job_form_certs")}</label>
        <CertificationMultiPicker
          t={t}
          selected={certs}
          onChange={setCerts}
          inputClassName={inputClass}
          addButtonClassName={chipBtn}
          chipButtonClassName={chipTag}
        />
      </div>

      <div>
        <label className={labelClass}>{t("job_form_uniform_equipment")}</label>
        <textarea className={`${inputClass} min-h-[80px]`} value={uniform} onChange={(e) => setUniform(e.target.value)} />
      </div>
      <div>
        <label className={labelClass}>{t("job_form_special_instructions")}</label>
        <textarea className={`${inputClass} min-h-[80px]`} value={special} onChange={(e) => setSpecial(e.target.value)} />
      </div>

      <div className={sectionBox}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className={sectionTitle}>{t("job_match_weights_title")}</h3>
            <p className={hint}>{t("job_match_weights_hint")}</p>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={customizeMatchWeights}
              onChange={(e) => {
                const checked = e.target.checked;
                setCustomizeMatchWeights(checked);
                if (checked) setMatchWeights(defaultMatchWeights);
              }}
            />
            {t("job_match_weights_customize")}
          </label>
        </div>
        <MatchWeightFields t={t} value={matchWeights} onChange={setMatchWeights} disabled={!customizeMatchWeights} />
        <p className={hint}>
          {customizeMatchWeights ? t("job_match_weights_override_active") : t("job_match_weights_using_defaults")}
        </p>
      </div>

      <div className={sectionBox}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className={sectionTitle}>{t("job_auto_dispatch_title")}</h3>
            <p className={hint}>{t("job_auto_dispatch_hint")}</p>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={automaticDispatchEnabled}
              onChange={(e) => setAutomaticDispatchEnabled(e.target.checked)}
            />
            {t("job_auto_dispatch_enable")}
          </label>
        </div>

        {automaticDispatchEnabled && (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className={labelClass}>{t("job_auto_dispatch_mode")}</label>
              <select
                className={inputClass}
                value={automaticDispatchMode}
                onChange={(e) => setAutomaticDispatchMode(e.target.value as AutomaticDispatchMode)}
              >
                <option value="fcfs">{t("job_auto_dispatch_mode_fcfs")}</option>
                <option value="performance_priority">{t("job_auto_dispatch_mode_performance")}</option>
                <option value="preferred_priority">{t("job_auto_dispatch_mode_preferred")}</option>
              </select>
            </div>

            {automaticDispatchMode === "performance_priority" && (
              <div className="sm:col-span-2">
                <label className={labelClass}>{t("job_auto_dispatch_elite_exclusive_hours")}</label>
                <input
                  className={inputClass}
                  type="number"
                  min="0"
                  step="0.25"
                  value={automaticDispatchEliteExclusiveHours}
                  onChange={(e) => setAutomaticDispatchEliteExclusiveHours(e.target.value)}
                />
                <p className={`${hint} mt-1`}>{t("job_auto_dispatch_elite_exclusive_hours_hint")}</p>
              </div>
            )}
          </div>
        )}
      </div>

      <div className={sectionBox}>
        <h3 className={sectionTitle}>{t("job_form_shifts")}</h3>
        <p className={hint}>{t("job_form_shifts_hint")}</p>
        {shifts.map((row, idx) => (
          <div key={idx} className={`grid gap-2 sm:grid-cols-12 items-end ${rowBorder}`}>
            <div className="sm:col-span-4">
              <label className={labelClass}>{t("job_form_shift_start")}</label>
              <input
                type="datetime-local"
                className={inputClass}
                value={row.starts_local}
                onChange={(e) => {
                  const next = [...shifts];
                  next[idx] = { ...row, starts_local: e.target.value };
                  setShifts(next);
                }}
              />
            </div>
            <div className="sm:col-span-4">
              <label className={labelClass}>{t("job_form_shift_end")}</label>
              <input
                type="datetime-local"
                className={inputClass}
                value={row.ends_local}
                onChange={(e) => {
                  const next = [...shifts];
                  next[idx] = { ...row, ends_local: e.target.value };
                  setShifts(next);
                }}
              />
            </div>
            <div className="sm:col-span-2">
              <label className={labelClass}>{t("job_form_workers")}</label>
              <input
                type="number"
                min={1}
                className={inputClass}
                value={row.workers_required}
                onChange={(e) => {
                  const next = [...shifts];
                  next[idx] = { ...row, workers_required: parseInt(e.target.value, 10) || 1 };
                  setShifts(next);
                }}
              />
            </div>
            <div className="sm:col-span-2 flex gap-1 flex-wrap">
              <button type="button" className={linkish} onClick={() => setShifts([...shifts, { ...row }])}>
                {t("job_form_duplicate_shift")}
              </button>
              <button
                type="button"
                className={`${dangerLink} disabled:opacity-40`}
                disabled={shifts.length <= 1}
                onClick={() => setShifts(shifts.filter((_, j) => j !== idx))}
              >
                {t("job_form_remove_shift")}
              </button>
            </div>
          </div>
        ))}
        <button type="button" className={addShiftText} onClick={() => setShifts([...shifts, defaultShiftRow()])}>
          + {t("job_form_add_shift")}
        </button>

        <div className={rangeBar}>
          <p className={rangeMuted}>{t("job_form_day_range")}</p>
          <p className={hint}>{t("job_form_day_range_hint")}</p>
          <div className="flex flex-wrap gap-2 items-end">
            <div>
              <label className={labelClass}>{t("job_form_range_from")}</label>
              <input type="date" className={inputClass} value={rangeFrom} onChange={(e) => setRangeFrom(e.target.value)} />
            </div>
            <div>
              <label className={labelClass}>{t("job_form_range_to")}</label>
              <input type="date" className={inputClass} value={rangeTo} onChange={(e) => setRangeTo(e.target.value)} />
            </div>
            <div>
              <label className={labelClass}>{t("job_form_workers")}</label>
              <input type="number" min={1} className={`${inputClass} w-24`} value={rangeWorkers} onChange={(e) => setRangeWorkers(e.target.value)} />
            </div>
            <button type="button" className={applyRangeBtn} onClick={addRangeShifts}>
              {t("job_form_apply_range")}
            </button>
          </div>
        </div>
      </div>

      <details className={detailsBox}>
        <summary className={summaryText}>{t("job_form_advanced")}</summary>
        <div className="grid gap-3 mt-3 sm:grid-cols-2">
          <div>
            <label className={labelClass}>{t("job_form_geofence")}</label>
            <input className={inputClass} type="number" min={0} value={geofence} onChange={(e) => setGeofence(e.target.value)} />
          </div>
          <div>
            <label className={labelClass}>{t("job_form_acceptance_window")}</label>
            <input className={inputClass} type="number" min={1} value={acceptanceMins} onChange={(e) => setAcceptanceMins(e.target.value)} />
          </div>
        </div>
      </details>

      {error && <p className={errText}>{error}</p>}
      <button type="submit" disabled={submitting} className={submitBtn}>
        {submitting ? "…" : t("job_form_submit")}
      </button>
    </form>
  );
}
