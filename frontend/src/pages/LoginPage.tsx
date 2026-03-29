import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { api, setSession } from "../api";

export default function LoginPage() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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

  return (
    <div className="max-w-md mx-auto space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-white">{t("login")}</h1>
        <p className="text-sm text-slate-400 mt-2">{t("login_username_password_hint")}</p>
      </div>

      <label className="block text-sm text-slate-400">{t("username")}</label>
      <input
        className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-3 text-lg"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        autoComplete="username"
      />
      <label className="block text-sm text-slate-400">{t("password")}</label>
      <input
        type="password"
        className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-3 text-lg"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete="current-password"
      />
      <button
        type="button"
        className="w-full bg-sky-600 hover:bg-sky-500 rounded-xl py-3 font-semibold text-slate-950"
        onClick={submit}
        disabled={loading}
      >
        {t("login")}
      </button>
      {msg && <p className="text-sm text-amber-300 whitespace-pre-wrap">{msg}</p>}
      <p className="text-xs text-slate-500 whitespace-pre-line">{t("login_demo_accounts")}</p>
      <button
        type="button"
        className="w-full text-sm text-sky-400 underline py-2"
        onClick={() => nav("/worker/welcome")}
      >
        {t("worker_onboarding_link")}
      </button>
    </div>
  );
}
