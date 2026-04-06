import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { api, setSession } from "../api";
import AuthShell from "../components/portal/AuthShell";

function MatIcon({ name, className = "" }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`.trim()} aria-hidden>{name}</span>;
}

export default function LoginPage() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const [mode, setMode] = useState<"worker" | "client" | "staff">("worker");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [otpStep, setOtpStep] = useState<"email" | "code">("email");
  const [devHint, setDevHint] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const inputClass =
    "w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-4 py-3 text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-2 focus:ring-primary";

  async function submit() {
    setLoading(true);
    setMsg(null);
    try {
      const r = await api<{ access_token: string; role: string }>("/auth/login", {
        method: "POST",
        json: { username: username.trim(), password },
      });
      setSession(r.access_token, r.role);
      if (r.role === "worker") nav("/worker");
      else if (r.role === "client") nav("/client");
      else nav("/ta");
    } catch (e) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function sendOtp() {
    setMsg(null);
    setDevHint(null);
    if (!email.trim()) {
      setMsg("Enter your email address.");
      return;
    }
    setLoading(true);
    try {
      const locale = i18n.language.startsWith("zh") ? "zh" : "en";
      const endpoint = mode === "client" ? "/auth/client/email-otp/request" : "/auth/worker/email-otp/request";
      const r = await api<{ dev_code?: string | null }>(endpoint, {
        method: "POST",
        json: { email: email.trim(), locale },
      });
      if (r.dev_code) setDevHint(`Dev code: ${r.dev_code}`);
      setOtpStep("code");
    } catch (e) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function verifyOtp() {
    setMsg(null);
    if (!code.trim()) {
      setMsg("Enter the verification code.");
      return;
    }
    setLoading(true);
    try {
      const locale = i18n.language.startsWith("zh") ? "zh" : "en";
      const endpoint = mode === "client" ? "/auth/client/email-otp/verify" : "/auth/worker/email-otp/verify";
      const r = await api<{ access_token: string; role: string }>(endpoint, {
        method: "POST",
        json: { email: email.trim(), code: code.trim(), locale },
      });
      setSession(r.access_token, r.role);
      if (r.role === "worker") nav("/worker");
      else nav("/client");
    } catch (e) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell eyebrow={t("login_eyebrow")} title={t("login")} description={t("login_username_password_hint")}>
      <div className="rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-6 shadow-sm md:p-8">
        <div className="mb-4 grid grid-cols-3 gap-2 rounded-xl bg-surface-container-low p-1">
          {[
            { id: "worker", label: "Worker" },
            { id: "client", label: "Client" },
            { id: "staff", label: "TA/Admin" },
          ].map((m) => (
            <button
              key={m.id}
              type="button"
              className={`rounded-lg px-2 py-2 text-xs font-semibold ${mode === m.id ? "bg-primary text-on-primary" : "text-on-surface-variant"}`}
              onClick={() => {
                setMode(m.id as "worker" | "client" | "staff");
                setMsg(null);
                setOtpStep("email");
                setCode("");
                setDevHint(null);
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
        <div className="space-y-4">
          {mode === "staff" ? (
            <>
              <div>
                <label className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
                  <MatIcon name="person" className="text-base text-primary" />
                  {t("username")}
                </label>
                <input
                  className={inputClass}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                />
              </div>
              <div>
                <label className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
                  <MatIcon name="lock" className="text-base text-primary" />
                  {t("password")}
                </label>
                <input
                  type="password"
                  className={inputClass}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
              </div>
              <button
                type="button"
                className="w-full rounded-xl bg-primary px-6 py-3.5 text-sm font-bold text-on-primary shadow-sm transition-colors hover:bg-primary-dim disabled:opacity-50"
                onClick={() => void submit()}
                disabled={loading}
              >
                {loading ? "…" : t("login")}
              </button>
            </>
          ) : (
            <>
              {otpStep === "email" ? (
                <>
                  <div>
                    <label className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
                      <MatIcon name="mail" className="text-base text-primary" />
                      Email
                    </label>
                    <input
                      type="email"
                      className={inputClass}
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      autoComplete="email"
                    />
                  </div>
                  <button
                    type="button"
                    className="w-full rounded-xl bg-primary px-6 py-3.5 text-sm font-bold text-on-primary shadow-sm transition-colors hover:bg-primary-dim disabled:opacity-50"
                    onClick={() => void sendOtp()}
                    disabled={loading}
                  >
                    {loading ? "…" : "Send verification code"}
                  </button>
                </>
              ) : (
                <>
                  <p className="text-sm text-on-surface-variant">
                    Verification code sent to <span className="font-semibold text-primary">{email.trim()}</span>
                  </p>
                  {devHint ? <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950">{devHint}</p> : null}
                  <input
                    className={`${inputClass} text-center text-lg tracking-[0.35em]`}
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 10))}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    placeholder="••••••"
                  />
                  <button
                    type="button"
                    className="w-full rounded-xl bg-primary px-6 py-3.5 text-sm font-bold text-on-primary shadow-sm transition-colors hover:bg-primary-dim disabled:opacity-50"
                    onClick={() => void verifyOtp()}
                    disabled={loading}
                  >
                    {loading ? "…" : "Verify and login"}
                  </button>
                  <button
                    type="button"
                    className="w-full py-2 text-sm font-semibold text-primary underline-offset-2 hover:underline"
                    onClick={() => {
                      setOtpStep("email");
                      setCode("");
                      setDevHint(null);
                    }}
                  >
                    Use a different email
                  </button>
                </>
              )}
            </>
          )}
          {msg && (
            <p className="rounded-xl border border-error-container/50 bg-error-container/15 px-3 py-2 text-sm text-error whitespace-pre-wrap">
              {msg}
            </p>
          )}
        </div>

        <div className="mt-8 flex flex-col gap-3 border-t border-outline-variant/15 pt-6">
          <Link
            to="/worker/signup"
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-primary/25 bg-primary-container/40 py-3 text-sm font-bold text-on-primary-container transition-colors hover:bg-primary-container/70"
          >
            <MatIcon name="person_add" className="text-lg" />
            {t("login_register")}
          </Link>
          <p className="text-center text-xs text-on-surface-variant">{t("login_register_hint")}</p>
          <Link
            to="/client/signup"
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-primary/25 bg-primary-container/20 py-3 text-sm font-bold text-on-primary-container transition-colors hover:bg-primary-container/50"
          >
            <MatIcon name="business" className="text-lg" />
            {t("login_register_client")}
          </Link>
          <p className="text-center text-xs text-on-surface-variant">{t("login_register_client_hint")}</p>
        </div>
      </div>
    </AuthShell>
  );
}
