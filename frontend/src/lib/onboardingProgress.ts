/** Mirrors backend `_weighted_completeness` for instant UI updates (0–100). */

export type OnboardingDraft = {
  fullName: string;
  nric: string;
  phone: string;
  email: string;
  languages: string[];
  jobTypes: string[];
  availability: Record<string, unknown>;
  skills: string[];
  certifications: string[];
  bankAccount: string;
  bankName: string;
  workPassNa: boolean;
  locationLat: number | null;
  locationLng: number | null;
  docTypes: Set<string>;
};

export function computeOnboardingProgress(d: OnboardingDraft): number {
  let s = 0;
  if (d.fullName.trim()) s += 5;
  if (d.nric.trim()) s += 5;
  if (d.phone.trim()) s += 5;
  if (d.email.trim()) s += 5;

  if (d.languages.length) s += 5;
  if (d.jobTypes.length) s += 5;
  if (d.availability && Object.keys(d.availability).length > 0) s += 5;
  if (d.skills.length) s += 5;

  if (d.bankAccount.replace(/\s/g, "").length >= 6) s += 15;

  const dt = d.docTypes;
  if (dt.has("nric_copy") || dt.has("nric")) s += 10;
  if (dt.has("work_pass") || d.workPassNa) s += 8;
  if (dt.has("certification") || dt.has("certifications")) s += 8.5;
  if (dt.has("training_record") || dt.has("training")) s += 8.5;

  if (d.certifications.length) s += 4;
  if (d.bankName.trim()) s += 2;
  if (d.locationLat != null && d.locationLng != null) s += 4;

  return Math.min(100, Math.round(s));
}

export function progressHint(pct: number, t: (k: string) => string): string {
  if (pct < 25) return t("onb_hint_low");
  if (pct < 60) return t("onb_hint_mid");
  if (pct < 90) return t("onb_hint_high");
  return t("onb_hint_almost");
}

export function progressBarClass(pct: number): string {
  if (pct < 33) return "from-amber-600 to-orange-500";
  if (pct < 66) return "from-sky-600 to-cyan-500";
  return "from-emerald-600 to-teal-400";
}
