import type { Dispatch, SetStateAction } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { api, getToken } from "../../api";
import { JobTypeMultiPicker } from "../../components/jobTypes/JobTypeMultiPicker";
import { DEFAULT_MAP_CENTER, LocationMapPicker } from "../../components/maps/LocationMapPicker";
import { isAllowedJobType } from "../../constants/jobTypes";
import {
  computeOnboardingProgress,
  progressBarClass,
  progressHint,
  type OnboardingDraft,
} from "../../lib/onboardingProgress";

const DRAFT_KEY = "mci_onboarding_draft_v1";

type Profile = {
  full_name: string;
  nric_masked: string | null;
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
  onboarding_completed: boolean;
};

const DOC_SLOTS = ["nric_copy", "work_pass", "certification", "training_record"] as const;

function maskBank(s: string): string {
  const d = s.replace(/\s/g, "");
  if (d.length <= 4) return "••••";
  return "••••••" + d.slice(-4);
}

export default function WorkerOnboardingPage() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const [step, setStep] = useState(1);
  const [fullName, setFullName] = useState("");
  const [nric, setNric] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [langs, setLangs] = useState<string[]>([]);
  const [langInput, setLangInput] = useState("");
  const [jobTypes, setJobTypes] = useState<string[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [skillInput, setSkillInput] = useState("");
  const [certs, setCerts] = useState<string[]>([]);
  const [certInput, setCertInput] = useState("");
  const [availMorning, setAvailMorning] = useState(false);
  const [availEvening, setAvailEvening] = useState(false);
  const [availWeekend, setAvailWeekend] = useState(false);
  const [bankAccount, setBankAccount] = useState("");
  const [bankName, setBankName] = useState("");
  const [workPassNa, setWorkPassNa] = useState(false);
  const [mapLat, setMapLat] = useState(DEFAULT_MAP_CENTER.lat);
  const [mapLng, setMapLng] = useState(DEFAULT_MAP_CENTER.lng);
  const [docTypes, setDocTypes] = useState<Set<string>>(new Set());
  const [uploadPct, setUploadPct] = useState<Record<string, number>>({});
  const [terms, setTerms] = useState(false);
  const [pdpa, setPdpa] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [serverPct, setServerPct] = useState<number | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const availability = useMemo(
    () => ({
      morning: availMorning,
      evening: availEvening,
      weekend: availWeekend,
    }),
    [availMorning, availEvening, availWeekend],
  );

  const draft: OnboardingDraft = useMemo(
    () => ({
      fullName,
      nric,
      phone,
      email,
      languages: langs,
      jobTypes,
      availability,
      skills,
      certifications: certs,
      bankAccount,
      bankName,
      workPassNa,
      locationLat: mapLat,
      locationLng: mapLng,
      docTypes,
    }),
    [
      fullName,
      nric,
      phone,
      email,
      langs,
      jobTypes,
      availability,
      skills,
      certs,
      bankAccount,
      bankName,
      workPassNa,
      mapLat,
      mapLng,
      docTypes,
    ],
  );

  const uiPct = computeOnboardingProgress(draft);
  const pct = serverPct ?? uiPct;

  const persistDraftLocal = useCallback(() => {
    try {
      localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({
          step,
          fullName,
          nric,
          phone,
          email,
          langs,
          jobTypes,
          skills,
          certs,
          availMorning,
          availEvening,
          availWeekend,
          bankAccount,
          bankName,
          workPassNa,
          mapLat,
          mapLng,
        }),
      );
    } catch {
      /* ignore */
    }
  }, [
    step,
    fullName,
    nric,
    phone,
    email,
    langs,
    jobTypes,
    skills,
    certs,
    availMorning,
    availEvening,
    availWeekend,
    bankAccount,
    bankName,
    workPassNa,
    mapLat,
    mapLng,
  ]);

  const saveRemote = useCallback(async () => {
    if (!getToken()) return;
    try {
      const p = await api<Profile>("/workers/me/profile", {
        method: "PUT",
        json: {
          full_name: fullName,
          nric: nric || undefined,
          email: email || undefined,
          phone: phone || undefined,
          languages: langs,
          job_type_preferences: jobTypes,
          skills,
          certifications: certs,
          availability,
          bank_account: bankAccount || undefined,
          bank_name: bankName || undefined,
          work_pass_not_applicable: workPassNa,
          location_lat: mapLat,
          location_lng: mapLng,
        },
      });
      setServerPct(p.profile_completeness_pct);
    } catch {
      /* silent autosave */
    }
  }, [
    fullName,
    nric,
    email,
    langs,
    jobTypes,
    skills,
    certs,
    availability,
    bankAccount,
    bankName,
    workPassNa,
    mapLat,
    mapLng,
  ]);

  useEffect(() => {
    persistDraftLocal();
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      saveRemote();
    }, 800);
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, [persistDraftLocal, saveRemote]);

  useEffect(() => {
    (async () => {
      try {
        let mapFromDraft = false;
        const raw = localStorage.getItem(DRAFT_KEY);
        if (raw) {
          const d = JSON.parse(raw);
          if (d.step) setStep(d.step);
          if (d.fullName != null) setFullName(d.fullName);
          if (d.nric != null) setNric(d.nric);
          if (d.phone != null) setPhone(d.phone);
          if (d.email != null) setEmail(d.email);
          if (Array.isArray(d.langs)) setLangs(d.langs);
          if (Array.isArray(d.jobTypes)) setJobTypes(d.jobTypes.filter(isAllowedJobType));
          if (Array.isArray(d.skills)) setSkills(d.skills);
          if (Array.isArray(d.certs)) setCerts(d.certs);
          if (typeof d.availMorning === "boolean") setAvailMorning(d.availMorning);
          if (typeof d.availEvening === "boolean") setAvailEvening(d.availEvening);
          if (typeof d.availWeekend === "boolean") setAvailWeekend(d.availWeekend);
          if (d.bankAccount != null) setBankAccount(d.bankAccount);
          if (d.bankName != null) setBankName(d.bankName);
          if (typeof d.workPassNa === "boolean") setWorkPassNa(d.workPassNa);
          if (typeof d.mapLat === "number" && Number.isFinite(d.mapLat) && typeof d.mapLng === "number" && Number.isFinite(d.mapLng)) {
            setMapLat(d.mapLat);
            setMapLng(d.mapLng);
            mapFromDraft = true;
          } else if (d.lat != null && d.lng != null) {
            const la = typeof d.lat === "number" ? d.lat : parseFloat(String(d.lat));
            const ln = typeof d.lng === "number" ? d.lng : parseFloat(String(d.lng));
            if (Number.isFinite(la) && Number.isFinite(ln)) {
              setMapLat(la);
              setMapLng(ln);
              mapFromDraft = true;
            }
          }
        }
        const p = await api<Profile>("/workers/me/profile");
        setServerPct(p.profile_completeness_pct);
        setFullName((x) => x || p.full_name || "");
        setPhone((x) => x || p.phone || "");
        setEmail((x) => x || p.email || "");
        setLangs((x) => (x.length ? x : p.languages || []));
        setJobTypes((x) =>
          x.length ? x.filter(isAllowedJobType) : (p.job_type_preferences || []).filter(isAllowedJobType),
        );
        setSkills((x) => (x.length ? x : p.skills || []));
        setCerts((x) => (x.length ? x : p.certifications || []));
        const a = p.availability || {};
        if (a.morning) setAvailMorning(true);
        if (a.evening) setAvailEvening(true);
        if (a.weekend) setAvailWeekend(true);
        setBankName((x) => x || p.bank_name || "");
        setWorkPassNa(p.work_pass_not_applicable);
        if (!mapFromDraft && p.location_lat != null && p.location_lng != null) {
          setMapLat(p.location_lat);
          setMapLng(p.location_lng);
        }
        const docs = await api<{ doc_type: string }[]>("/workers/me/documents");
        setDocTypes(new Set(docs.map((d) => d.doc_type)));
        if (p.onboarding_completed) nav("/worker", { replace: true });
      } catch {
        /* ignore */
      }
    })();
  }, []);

  function addChip(val: string, setList: Dispatch<SetStateAction<string[]>>, setInp: (s: string) => void) {
    const v = val.trim();
    if (!v) return;
    setList((prev) => (prev.includes(v) ? prev : [...prev, v]));
    setInp("");
  }

  async function uploadFile(docType: string, file: File) {
    setMsg(null);
    const token = getToken();
    const fd = new FormData();
    fd.append("file", file);
    setUploadPct((m) => ({ ...m, [docType]: 5 }));
    const tick = window.setInterval(() => {
      setUploadPct((m) => {
        const c = m[docType] ?? 0;
        return { ...m, [docType]: Math.min(92, c + 12) };
      });
    }, 120);
    try {
      const res = await fetch(`/api/workers/me/documents?doc_type=${encodeURIComponent(docType)}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      clearInterval(tick);
      if (!res.ok) throw new Error(await res.text());
      setUploadPct((m) => ({ ...m, [docType]: 100 }));
      setDocTypes((prev) => new Set([...prev, docType]));
      const p = await api<Profile>("/workers/me/profile");
      setServerPct(p.profile_completeness_pct);
    } catch (e) {
      clearInterval(tick);
      setMsg(String(e));
      setUploadPct((m) => ({ ...m, [docType]: 0 }));
    }
  }

  async function finish() {
    setMsg(null);
    try {
      if (!terms || !pdpa) {
        setMsg(t("onb_review_must_accept"));
        return;
      }
      await saveRemote();
      if (pdpa) await api("/workers/me/pdpa-consent", { method: "POST" });
      await api("/workers/me/onboarding/complete", {
        method: "POST",
        json: { terms_accepted: true },
      });
      localStorage.removeItem(DRAFT_KEY);
      setStep(6);
    } catch (e) {
      setMsg(String(e));
    }
  }

  const barClass = progressBarClass(pct);

  return (
    <div className="flex flex-col flex-1 min-h-0 -mx-1">
      <div className="sticky top-0 z-20 bg-slate-950/95 backdrop-blur border-b border-slate-800 px-4 py-3">
        <div className="flex justify-between items-center text-xs text-slate-400 mb-1">
          <span>{t("onb_progress_label")}</span>
          <span className="text-sky-300 font-mono">{pct}%</span>
        </div>
        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
          <div
            className={`h-full bg-gradient-to-r transition-all duration-500 ease-out ${barClass}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="text-[11px] text-slate-500 mt-1.5 leading-snug">{progressHint(pct, t)}</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 pb-28">
        {step === 1 && (
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-white">{t("onb_step_basic")}</h2>
            <label className="text-xs text-slate-500">{t("wizard_name")}</label>
            <input
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
            <label className="text-xs text-slate-500">{t("onb_nric")}</label>
            <input
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 tracking-wider"
              value={nric}
              onChange={(e) => setNric(e.target.value)}
              placeholder="S1234567D"
            />
            <label className="text-xs text-slate-500">{t("phone")}</label>
            <input
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
            <label className="text-xs text-slate-500">Email</label>
            <input
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-white">{t("onb_step_prefs")}</h2>
            <label className="text-xs text-slate-500">{t("wizard_languages")}</label>
            <div className="flex gap-2">
              <input
                className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-3 py-2"
                value={langInput}
                onChange={(e) => setLangInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addChip(langInput, setLangs, setLangInput)}
              />
              <button type="button" className="px-3 bg-slate-800 rounded-xl text-sm" onClick={() => addChip(langInput, setLangs, setLangInput)}>
                +
              </button>
            </div>
            <div className="flex flex-wrap gap-1">
              {langs.map((l) => (
                <span key={l} className="text-xs bg-slate-800 px-2 py-1 rounded-lg">
                  {l}
                </span>
              ))}
            </div>
            <label className="text-xs text-slate-500">{t("wizard_job_types")}</label>
            <JobTypeMultiPicker
              t={t}
              selected={jobTypes}
              onChange={setJobTypes}
              selectClassName="flex-1 min-w-0 bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-sm"
              addButtonClassName="px-3 bg-slate-800 rounded-xl text-sm shrink-0"
              chipButtonClassName="text-xs bg-slate-800 px-2 py-1 rounded-lg"
            />
            <p className="text-xs text-slate-500">{t("onb_availability")}</p>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={availMorning} onChange={(e) => setAvailMorning(e.target.checked)} />
              {t("onb_av_morning")}
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={availEvening} onChange={(e) => setAvailEvening(e.target.checked)} />
              {t("onb_av_evening")}
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={availWeekend} onChange={(e) => setAvailWeekend(e.target.checked)} />
              {t("onb_av_weekend")}
            </label>
            <label className="text-xs text-slate-500">{t("wizard_skills")}</label>
            <div className="flex gap-2">
              <input
                className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-3 py-2"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addChip(skillInput, setSkills, setSkillInput)}
              />
              <button type="button" className="px-3 bg-slate-800 rounded-xl text-sm" onClick={() => addChip(skillInput, setSkills, setSkillInput)}>
                +
              </button>
            </div>
            <div className="flex flex-wrap gap-1">
              {skills.map((l) => (
                <span key={l} className="text-xs bg-slate-800 px-2 py-1 rounded-lg">
                  {l}
                </span>
              ))}
            </div>
            <label className="text-xs text-slate-500">{t("onb_certs_optional")}</label>
            <div className="flex gap-2">
              <input
                className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-3 py-2"
                value={certInput}
                onChange={(e) => setCertInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addChip(certInput, setCerts, setCertInput)}
              />
              <button type="button" className="px-3 bg-slate-800 rounded-xl text-sm" onClick={() => addChip(certInput, setCerts, setCertInput)}>
                +
              </button>
            </div>
            <div className="flex flex-wrap gap-1">
              {certs.map((l) => (
                <span key={l} className="text-xs bg-slate-800 px-2 py-1 rounded-lg">
                  {l}
                </span>
              ))}
            </div>
            <label className="text-xs text-slate-500">{t("wizard_location")}</label>
            <LocationMapPicker
              latitude={mapLat}
              longitude={mapLng}
              onChange={({ lat, lng }) => {
                setMapLat(lat);
                setMapLng(lng);
              }}
              lightMode={false}
              height="220px"
              showGeolocationButton={false}
            />
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-white">{t("onb_step_bank")}</h2>
            <label className="text-xs text-slate-500">{t("onb_bank_account")}</label>
            <input
              type="password"
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2"
              value={bankAccount}
              onChange={(e) => setBankAccount(e.target.value)}
              autoComplete="off"
            />
            <label className="text-xs text-slate-500">{t("onb_bank_name_optional")}</label>
            <input className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2" value={bankName} onChange={(e) => setBankName(e.target.value)} />
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-white">{t("onb_step_docs")}</h2>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={workPassNa} onChange={(e) => setWorkPassNa(e.target.checked)} />
              {t("onb_work_pass_na")}
            </label>
            {DOC_SLOTS.map((slot) => (
              <div key={slot} className="border border-slate-800 rounded-xl p-3 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-slate-200">{t(`onb_doc_${slot}`)}</span>
                  {docTypes.has(slot) && <span className="text-xs text-emerald-400">{t("onb_uploaded")}</span>}
                </div>
                <input
                  type="file"
                  accept="image/*,.pdf,application/pdf"
                  capture="environment"
                  className="text-xs w-full"
                  disabled={slot === "work_pass" && workPassNa}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) uploadFile(slot, f);
                    e.target.value = "";
                  }}
                />
                {(uploadPct[slot] ?? 0) > 0 && (uploadPct[slot] ?? 0) < 100 && (
                  <div className="h-1 bg-slate-800 rounded overflow-hidden">
                    <div className="h-full bg-sky-500 transition-all" style={{ width: `${uploadPct[slot]}%` }} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {step === 5 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-white">{t("onb_step_review")}</h2>
            <div className="text-sm space-y-2 text-slate-300">
              <p>
                <span className="text-slate-500">{t("wizard_name")}:</span> {fullName || "—"}
              </p>
              <p>
                <span className="text-slate-500">{t("onb_nric")}:</span> {nric ? "••••" + nric.slice(-4) : "—"}
              </p>
              <p>
                <span className="text-slate-500">{t("phone")}:</span> {phone || "—"}
              </p>
              <p>
                <span className="text-slate-500">Email:</span> {email || "—"}
              </p>
              <p>
                <span className="text-slate-500">{t("wizard_languages")}:</span> {langs.join(", ") || "—"}
              </p>
              <p>
                <span className="text-slate-500">{t("wizard_job_types")}:</span> {jobTypes.join(", ") || "—"}
              </p>
              <p>
                <span className="text-slate-500">{t("onb_bank_account")}:</span> {bankAccount ? maskBank(bankAccount) : "—"}
              </p>
              <p>
                <span className="text-slate-500">{t("onb_documents")}:</span> {[...docTypes].join(", ") || "—"}
              </p>
            </div>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} className="mt-1" />
              {t("onb_terms")}
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={pdpa} onChange={(e) => setPdpa(e.target.checked)} className="mt-1" />
              {t("wizard_pdpa")}
            </label>
          </div>
        )}

        {step === 6 && (
          <div className="text-center py-8 space-y-4">
            <div className="text-4xl">✓</div>
            <h2 className="text-xl font-bold text-white">{t("onb_done_title")}</h2>
            <p className="text-sm text-slate-400">{t("onb_done_body")}</p>
            <button type="button" className="bg-sky-600 text-slate-950 font-semibold px-6 py-3 rounded-xl" onClick={() => nav("/worker")}>
              {t("onb_done_cta")}
            </button>
          </div>
        )}

        {msg && <p className="text-sm text-red-400 mt-3">{msg}</p>}
      </div>

      {step >= 1 && step <= 5 && (
        <div className="sticky bottom-0 bg-slate-950/95 border-t border-slate-800 p-4 flex gap-2 mt-auto">
          {step > 1 && (
            <button type="button" className="flex-1 bg-slate-800 py-3 rounded-xl text-sm" onClick={() => setStep((s) => s - 1)}>
              {t("wizard_back")}
            </button>
          )}
          {step < 5 && (
            <button type="button" className="flex-1 bg-sky-600 text-slate-950 font-semibold py-3 rounded-xl text-sm" onClick={() => setStep((s) => s + 1)}>
              {t("wizard_next")}
            </button>
          )}
          {step === 5 && (
            <button type="button" className="flex-1 bg-emerald-600 text-slate-950 font-semibold py-3 rounded-xl text-sm" onClick={finish}>
              {t("onb_submit")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
