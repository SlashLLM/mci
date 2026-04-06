import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { api, setSession } from "../../api";
import AuthShell from "../../components/portal/AuthShell";

function MatIcon({ name, className = "" }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`.trim()} aria-hidden>{name}</span>;
}

type OtpRequestRes = {
  ok: boolean;
  message?: string;
  dev_code?: string | null;
  /** "dev" = no email sent; "resend" = API send attempted */
  delivery?: "dev" | "resend";
};
type VerifyRes = { access_token: string; role: string; locale?: string };

export default function WorkerSignupPage() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"email" | "code">("email");
  const [devHint, setDevHint] = useState<string | null>(null);
  const [deliveryKind, setDeliveryKind] = useState<"dev" | "resend" | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const inputClass =
    "w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-4 py-3 text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-2 focus:ring-primary";

  async function sendCode() {
    setMsg(null);
    setDevHint(null);
    setDeliveryKind(null);
    const em = email.trim();
    if (!em) {
      setMsg(t("worker_signup_email_required"));
      return;
    }
    setLoading(true);
    try {
      const locale = i18n.language.startsWith("zh") ? "zh" : "en";
      const r = await api<OtpRequestRes>("/auth/worker/email-otp/request", {
        method: "POST",
        json: { email: em, locale },
      });
      setDeliveryKind(r.delivery ?? (r.dev_code ? "dev" : "resend"));
      if (r.dev_code) setDevHint(t("worker_signup_email_dev_hint", { code: r.dev_code }));
      setStep("code");
    } catch (e) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function verify() {
    setMsg(null);
    const em = email.trim();
    if (!code.trim()) {
      setMsg(t("worker_signup_code_required"));
      return;
    }
    setLoading(true);
    try {
      const locale = i18n.language.startsWith("zh") ? "zh" : "en";
      const r = await api<VerifyRes>("/auth/worker/email-otp/verify", {
        method: "POST",
        json: { email: em, code: code.trim(), locale },
      });
      setSession(r.access_token, r.role);
      nav("/worker/onboarding", { replace: true });
    } catch (e) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      eyebrow={t("worker_signup_eyebrow")}
      title={t("worker_signup_title")}
      description={t("worker_signup_subtitle")}
    >
      <div className="rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-6 shadow-sm md:p-8">
        {step === "email" && (
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
                <MatIcon name="mail" className="text-base text-primary" />
                {t("worker_signup_email_label")}
              </label>
              <input
                type="email"
                autoComplete="email"
                className={inputClass}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>
            <button
              type="button"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3.5 text-sm font-bold text-on-primary shadow-sm transition-colors hover:bg-primary-dim disabled:opacity-50"
              onClick={() => void sendCode()}
            >
              <MatIcon name="send" className="text-lg" />
              {loading ? "…" : t("worker_signup_send_code")}
            </button>
            <p className="text-center text-xs text-on-surface-variant">{t("worker_signup_phone_coming")}</p>
          </div>
        )}

        {step === "code" && (
          <div className="space-y-4">
            <p className="text-sm text-on-surface-variant">
              {t("worker_signup_sent_to")}{" "}
              <span className="font-semibold text-primary">{email.trim()}</span>
            </p>
            {deliveryKind === "dev" ? (
              <p className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-950 dark:border-amber-800/60 dark:bg-amber-950/35 dark:text-amber-100">
                {t("worker_signup_delivery_dev_notice")}
              </p>
            ) : null}
            {deliveryKind === "resend" ? (
              <p className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-950 dark:border-sky-800/50 dark:bg-sky-950/30 dark:text-sky-100">
                {t("worker_signup_delivery_resend_hint")}
              </p>
            ) : null}
            {devHint ? (
              <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950 dark:border-amber-800/50 dark:bg-amber-950/30 dark:text-amber-100">
                {devHint}
              </p>
            ) : null}
            <div>
              <label className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
                <MatIcon name="pin" className="text-base text-primary" />
                {t("worker_signup_code_label")}
              </label>
              <input
                inputMode="numeric"
                autoComplete="one-time-code"
                className={`${inputClass} text-center text-lg tracking-[0.35em]`}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 10))}
                placeholder="••••••"
              />
            </div>
            <button
              type="button"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3.5 text-sm font-bold text-on-primary shadow-sm transition-colors hover:bg-primary-dim disabled:opacity-50"
              onClick={() => void verify()}
            >
              <MatIcon name="verified_user" className="text-lg" />
              {loading ? "…" : t("worker_signup_verify_continue")}
            </button>
            <button
              type="button"
              className="w-full py-2 text-sm font-semibold text-primary underline-offset-2 hover:underline"
              onClick={() => {
                setStep("email");
                setCode("");
                setDevHint(null);
                setDeliveryKind(null);
              }}
            >
              {t("worker_signup_change_email")}
            </button>
          </div>
        )}

        {msg ? (
          <p className="mt-4 rounded-xl border border-error-container/50 bg-error-container/15 px-3 py-2 text-sm text-error whitespace-pre-wrap">
            {msg}
          </p>
        ) : null}

        <p className="mt-6 border-t border-outline-variant/15 pt-6 text-center text-[11px] leading-relaxed text-on-surface-variant">
          {t("worker_signup_resend_note")}
        </p>

        <div className="mt-4 text-center">
          <Link
            to="/login"
            className="inline-flex items-center gap-2 text-sm font-semibold text-primary hover:text-primary-dim"
          >
            <MatIcon name="login" className="text-lg" />
            {t("worker_welcome_have_account")}
          </Link>
        </div>
      </div>
    </AuthShell>
  );
}
