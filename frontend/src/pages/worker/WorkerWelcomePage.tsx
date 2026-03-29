import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import WorkerMobileShell from "../../components/worker/WorkerMobileShell";

export default function WorkerWelcomePage() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();

  return (
    <WorkerMobileShell>
      <div className="flex flex-col flex-1 p-6 pt-10">
        <div className="flex justify-end gap-2 mb-6">
          <button
            type="button"
            className={`text-xs px-3 py-1 rounded-lg ${i18n.language.startsWith("zh") ? "bg-slate-800" : "bg-sky-600/30 text-sky-300"}`}
            onClick={() => {
              i18n.changeLanguage("en");
              localStorage.setItem("locale", "en");
            }}
          >
            English
          </button>
          <button
            type="button"
            className={`text-xs px-3 py-1 rounded-lg ${i18n.language.startsWith("zh") ? "bg-sky-600/30 text-sky-300" : "bg-slate-800"}`}
            onClick={() => {
              i18n.changeLanguage("zh");
              localStorage.setItem("locale", "zh");
            }}
          >
            简体中文
          </button>
        </div>
        <h1 className="text-2xl font-bold text-white leading-tight">{t("worker_welcome_title")}</h1>
        <p className="text-slate-400 mt-3 text-sm leading-relaxed">{t("worker_welcome_body")}</p>
        <div className="flex-1" />
        <button
          type="button"
          className="w-full bg-gradient-to-r from-sky-600 to-blue-600 text-slate-950 font-semibold py-4 rounded-xl mt-8"
          onClick={() => nav("/login")}
        >
          {t("worker_welcome_cta")}
        </button>
        <button type="button" className="text-center text-sm text-slate-500 underline mt-4" onClick={() => nav("/login")}>
          {t("worker_welcome_have_account")}
        </button>
      </div>
    </WorkerMobileShell>
  );
}
