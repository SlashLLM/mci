import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { DEFAULT_MAP_CENTER, LocationMapPicker } from "../../components/maps/LocationMapPicker";

type ClientProfile = {
  company_name: string;
  contact_name: string;
  contact_email: string | null;
  contact_phone: string | null;
  address_line: string | null;
  location_lat: number | null;
  location_lng: number | null;
  billing_notes: string | null;
  profile_completeness_pct: number;
  pdpa_consent: boolean;
  onboarding_completed: boolean;
};

function computeClientOnboardingProgress(profile: ClientProfile, termsChecked: boolean, pdpaChecked: boolean): number {
  let score = 0;
  if (profile.company_name?.trim()) score += 20;
  if (profile.contact_name?.trim()) score += 20;
  if (profile.contact_email?.trim()) score += 15;
  if (profile.contact_phone?.trim()) score += 15;
  if (profile.address_line?.trim()) score += 10;
  if (profile.location_lat != null && profile.location_lng != null) score += 5;
  if (profile.billing_notes?.trim()) score += 5;
  if (profile.pdpa_consent || pdpaChecked) score += 5;
  if (termsChecked) score += 5;
  return Math.min(100, score);
}

export default function ClientOnboardingPage() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const [step, setStep] = useState(1);
  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [terms, setTerms] = useState(false);
  const [pdpa, setPdpa] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api<ClientProfile>("/client/me/profile")
      .then((p) => {
        setProfile(p);
        if (p.onboarding_completed) nav("/client", { replace: true });
      })
      .catch((e) => setMsg(String(e)));
  }, [nav]);

  async function persistProfile(): Promise<boolean> {
    if (!profile) return false;
    try {
      const updated = await api<ClientProfile>("/client/me/profile", { method: "PUT", json: profile });
      setProfile(updated);
      return true;
    } catch (e) {
      setMsg(String(e));
      return false;
    }
  }

  async function goNext() {
    if (!profile || step >= 4) return;
    setMsg(null);
    setSaving(true);
    try {
      const ok = await persistProfile();
      if (ok) setStep((s) => s + 1);
    } finally {
      setSaving(false);
    }
  }

  async function saveProfile() {
    if (!profile) return;
    setMsg(null);
    if (!terms) {
      setMsg(t("client_onboarding_terms_required"));
      return;
    }
    setSaving(true);
    try {
      if (!(await persistProfile())) return;
      if (pdpa) await api("/client/me/pdpa-consent", { method: "POST" });
      await api("/client/me/onboarding/complete", { method: "POST", json: { terms_accepted: true } });
      setStep(5);
    } catch (e) {
      setMsg(String(e));
    } finally {
      setSaving(false);
    }
  }

  if (!profile) return <div className="p-6 text-sm text-on-surface-variant">{t("settings_loading")}</div>;

  const totalSteps = 4;
  const pct = computeClientOnboardingProgress(profile, terms, pdpa);
  const stepNav = [
    { index: 1, icon: "business", label: t("client_onboarding_company") },
    { index: 2, icon: "contacts", label: t("client_onboarding_contact_name") },
    { index: 3, icon: "location_on", label: t("client_onboarding_address") },
    { index: 4, icon: "task_alt", label: t("onb_step_review") },
  ];

  return (
    <div className="flex min-h-screen flex-col bg-surface text-on-surface">
      <header className="sticky top-0 z-40 h-16 border-b border-black/10 bg-white">
        <div className="mx-auto flex h-full max-w-[1440px] items-center justify-between px-4 md:px-8">
          <span className="truncate text-xl font-bold tracking-tight text-black">MCI Workforce</span>
          <div className="hidden items-center gap-4 md:flex" />
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="hidden w-72 shrink-0 flex-col gap-4 bg-[#f3f3f3] px-6 py-8 md:flex">
          <div className="mb-8">
            <h2 className="text-2xl font-headline font-extrabold tracking-tight text-on-surface">{t("client_onboarding_title")}</h2>
            <div className="mt-4">
              <div className="mb-2 flex items-end justify-between">
                <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">{pct}% Complete</span>
              </div>
              <div className="h-1 w-full overflow-hidden rounded-full bg-surface-container-highest">
                <div className="h-full bg-primary transition-all duration-300" style={{ width: `${pct}%` }} />
              </div>
            </div>
          </div>
          <nav className="flex flex-col gap-1">
            {stepNav.map((item) => {
              const active = item.index === step;
              return (
                <button
                  key={item.index}
                  type="button"
                  onClick={() => setStep(item.index)}
                  className={[
                    "flex items-center gap-3 rounded-pill px-4 py-3 text-left transition-all",
                    active
                      ? "translate-x-1 bg-black font-bold text-white"
                      : "text-on-surface-variant hover:bg-white/40",
                  ].join(" ")}
                >
                  <span className="material-symbols-outlined" style={{ fontVariationSettings: active ? "'FILL' 1" : "'FILL' 0" }}>
                    {item.icon}
                  </span>
                  <span className="text-sm">{item.label}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        <main className="flex-1 overflow-y-auto bg-surface-container-low px-4 py-8 md:px-16 md:py-12">
          <div className="mx-auto max-w-4xl">
            <header className="mb-10">
              <div className="mb-4 flex items-center gap-4">
                <span className="text-lg font-headline font-bold text-primary">{String(Math.min(step, totalSteps)).padStart(2, "0")}</span>
                <div className="h-px flex-1 bg-outline-variant/30" />
              </div>
              <h1 className="mb-2 text-4xl font-headline font-extrabold tracking-tight text-on-background md:text-5xl">
                {step === 1
                  ? t("client_onboarding_company")
                  : step === 2
                    ? t("client_onboarding_contact_name")
                    : step === 3
                      ? t("client_onboarding_address")
                      : t("onb_step_review")}
              </h1>
              <p className="max-w-xl text-on-surface-variant">{t("client_onboarding_subtitle")}</p>
            </header>

            <section className="relative overflow-hidden rounded-featured bg-surface-container-lowest p-6 shadow-card md:p-10">
              <div className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full bg-black/5 blur-3xl" />
              <div className="relative z-10">
                {step === 1 && (
                  <div className="space-y-4">
                    <label className="text-xs text-on-surface-variant">{t("client_onboarding_company")}</label>
                    <input
                      className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-lowest px-3 py-2 text-on-surface"
                      value={profile.company_name}
                      onChange={(e) => setProfile({ ...profile, company_name: e.target.value })}
                    />
                    <label className="text-xs text-on-surface-variant">{t("client_onboarding_billing")}</label>
                    <textarea
                      className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-lowest px-3 py-2 text-on-surface"
                      rows={3}
                      value={profile.billing_notes ?? ""}
                      onChange={(e) => setProfile({ ...profile, billing_notes: e.target.value || null })}
                    />
                  </div>
                )}

                {step === 2 && (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="text-xs text-on-surface-variant">{t("client_onboarding_contact_name")}</label>
                      <input
                        className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-lowest px-3 py-2 text-on-surface"
                        value={profile.contact_name}
                        onChange={(e) => setProfile({ ...profile, contact_name: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-on-surface-variant">{t("client_onboarding_contact_phone")}</label>
                      <input
                        className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-lowest px-3 py-2 text-on-surface"
                        value={profile.contact_phone ?? ""}
                        onChange={(e) => setProfile({ ...profile, contact_phone: e.target.value || null })}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs text-on-surface-variant">{t("client_onboarding_contact_email")}</label>
                      <input
                        type="email"
                        className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-lowest px-3 py-2 text-on-surface"
                        value={profile.contact_email ?? ""}
                        onChange={(e) => setProfile({ ...profile, contact_email: e.target.value || null })}
                      />
                    </div>
                  </div>
                )}

                {step === 3 && (
                  <div className="space-y-4">
                    <label className="text-xs text-on-surface-variant">{t("client_onboarding_address")}</label>
                    <textarea
                      className="w-full rounded-xl border border-outline-variant/30 bg-surface-container-lowest px-3 py-2 text-on-surface"
                      rows={2}
                      value={profile.address_line ?? ""}
                      onChange={(e) => setProfile({ ...profile, address_line: e.target.value || null })}
                    />
                    <LocationMapPicker
                      latitude={profile.location_lat ?? DEFAULT_MAP_CENTER.lat}
                      longitude={profile.location_lng ?? DEFAULT_MAP_CENTER.lng}
                      onChange={({ lat, lng }) => setProfile({ ...profile, location_lat: lat, location_lng: lng })}
                      lightMode
                      height="240px"
                    />
                  </div>
                )}

                {step === 4 && (
                  <div className="space-y-4">
                    <div className="text-sm space-y-2 text-on-surface-variant">
                      <p><span className="text-on-surface">{t("client_onboarding_company")}:</span> {profile.company_name || "—"}</p>
                      <p><span className="text-on-surface">{t("client_onboarding_contact_name")}:</span> {profile.contact_name || "—"}</p>
                      <p><span className="text-on-surface">{t("client_onboarding_contact_email")}:</span> {profile.contact_email || "—"}</p>
                      <p><span className="text-on-surface">{t("client_onboarding_contact_phone")}:</span> {profile.contact_phone || "—"}</p>
                      <p><span className="text-on-surface">{t("client_onboarding_address")}:</span> {profile.address_line || "—"}</p>
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

                {step === 5 && (
                  <div className="text-center py-8 space-y-4">
                    <div className="text-4xl text-primary">✓</div>
                    <h2 className="text-xl font-bold">{t("onb_done_title")}</h2>
                    <p className="text-sm text-on-surface-variant">{t("client_onboarding_subtitle")}</p>
                    <button type="button" className="bg-primary text-on-primary font-semibold px-10 py-4 rounded-xl" onClick={() => nav("/client")}>
                      {t("client_onboarding_done_cta")}
                    </button>
                  </div>
                )}

                {msg ? <p className="text-sm text-error mt-3">{msg}</p> : null}
              </div>
            </section>
          </div>
        </main>
      </div>

      {step >= 1 && step <= 4 && (
        <div className="sticky bottom-0 z-30 border-t border-outline-variant/20 bg-surface-container-lowest/95 p-4">
          <div className="mx-auto flex max-w-lg gap-2">
            {step > 1 && (
              <button
                type="button"
                className="flex-1 bg-surface-container-high py-3 rounded-xl text-sm font-semibold text-on-surface"
                onClick={() => setStep((s) => s - 1)}
              >
                {t("wizard_back")}
              </button>
            )}
            {step < 4 && (
              <button
                type="button"
                disabled={saving}
                className="flex-1 bg-primary text-on-primary font-semibold py-3 rounded-xl text-sm disabled:opacity-50"
                onClick={() => void goNext()}
              >
                {saving ? "…" : t("wizard_next")}
              </button>
            )}
            {step === 4 && (
              <button
                type="button"
                disabled={saving}
                className="flex-1 bg-primary text-on-primary font-semibold py-3 rounded-xl text-sm disabled:opacity-50"
                onClick={() => void saveProfile()}
              >
                {saving ? "…" : t("client_onboarding_submit")}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
