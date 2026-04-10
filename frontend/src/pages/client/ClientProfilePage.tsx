import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { DEFAULT_MAP_CENTER, LocationMapPicker } from "../../components/maps/LocationMapPicker";

type ClientProfilePayload = {
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
  terms_accepted: boolean;
  onboarding_completed: boolean;
};

export function ClientProfilePage() {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<ClientProfilePayload | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    document.title = `${t("client_profile_title")} | MCI Workforce`;
  }, [t]);

  useEffect(() => {
    setErr(null);
    api<ClientProfilePayload>("/client/me/profile")
      .then(setDraft)
      .catch((e) => setErr(String(e)));
  }, []);

  async function save() {
    if (!draft) return;
    setErr(null);
    setMsg(null);
    setSaving(true);
    try {
      const updated = await api<ClientProfilePayload>("/client/me/profile", {
        method: "PUT",
        json: {
          company_name: draft.company_name,
          contact_name: draft.contact_name,
          contact_email: draft.contact_email,
          contact_phone: draft.contact_phone,
          address_line: draft.address_line,
          location_lat: draft.location_lat,
          location_lng: draft.location_lng,
          billing_notes: draft.billing_notes,
        },
      });
      setDraft(updated);
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
    <div className="max-w-2xl">
      <h1 className="font-headline text-3xl md:text-4xl font-extrabold text-on-surface tracking-tight mb-2">
        {t("client_profile_title")}
      </h1>
      <p className="text-on-surface-variant text-sm mb-8">{t("client_profile_intro")}</p>
      {err && <p className="text-sm text-error mb-4">{err}</p>}
      {msg && <p className="text-sm text-primary mb-4">{msg}</p>}
      {!draft && !err ? (
        <p className="text-sm text-on-surface-variant">{t("job_detail_profile_loading")}</p>
      ) : draft ? (
        <div className="space-y-8">
          <div className="rounded-2xl border border-outline-variant/25 bg-surface-container-lowest p-6 space-y-4">
            <div>
              <label className="block text-xs font-medium text-on-surface-variant mb-1">{t("client_onboarding_company")}</label>
              <input
                type="text"
                className={inputClass}
                value={draft.company_name}
                onChange={(e) => setDraft({ ...draft, company_name: e.target.value })}
                autoComplete="organization"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-on-surface-variant mb-1">{t("client_onboarding_billing")}</label>
              <textarea
                className={`${inputClass} min-h-[5rem]`}
                rows={3}
                value={draft.billing_notes ?? ""}
                onChange={(e) => setDraft({ ...draft, billing_notes: e.target.value || null })}
              />
            </div>
          </div>

          <div className="rounded-2xl border border-outline-variant/25 bg-surface-container-lowest p-6 grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <label className="block text-xs font-medium text-on-surface-variant mb-1">{t("client_onboarding_contact_name")}</label>
              <input
                type="text"
                className={inputClass}
                value={draft.contact_name}
                onChange={(e) => setDraft({ ...draft, contact_name: e.target.value })}
                autoComplete="name"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-on-surface-variant mb-1">{t("client_onboarding_contact_phone")}</label>
              <input
                type="tel"
                className={inputClass}
                value={draft.contact_phone ?? ""}
                onChange={(e) => setDraft({ ...draft, contact_phone: e.target.value || null })}
                autoComplete="tel"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-on-surface-variant mb-1">{t("client_onboarding_contact_email")}</label>
              <input
                type="email"
                className={inputClass}
                value={draft.contact_email ?? ""}
                onChange={(e) => setDraft({ ...draft, contact_email: e.target.value || null })}
                autoComplete="email"
              />
            </div>
          </div>

          <div className="rounded-2xl border border-outline-variant/25 bg-surface-container-lowest p-6 space-y-4">
            <div>
              <label className="block text-xs font-medium text-on-surface-variant mb-1">{t("client_onboarding_address")}</label>
              <textarea
                className={`${inputClass} min-h-[4.5rem]`}
                rows={2}
                value={draft.address_line ?? ""}
                onChange={(e) => setDraft({ ...draft, address_line: e.target.value || null })}
              />
            </div>
            <LocationMapPicker
              latitude={draft.location_lat ?? DEFAULT_MAP_CENTER.lat}
              longitude={draft.location_lng ?? DEFAULT_MAP_CENTER.lng}
              onChange={({ lat, lng }) => setDraft({ ...draft, location_lat: lat, location_lng: lng })}
              lightMode
              height="240px"
            />
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <button
              type="button"
              disabled={saving}
              className="glass-cta text-white px-5 py-3 rounded-xl text-sm font-bold shadow-lg disabled:opacity-50"
              onClick={() => void save()}
            >
              {saving ? "…" : t("ta_profile_save")}
            </button>
            <p className="text-xs text-on-surface-variant">
              {t("client_profile_completeness", { pct: draft.profile_completeness_pct })}
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
