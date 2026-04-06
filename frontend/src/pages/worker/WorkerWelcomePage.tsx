import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import AuthShell from "../../components/portal/AuthShell";

function MatIcon({ name, className = "" }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`.trim()} aria-hidden>{name}</span>;
}

export default function WorkerWelcomePage() {
  const { t } = useTranslation();
  const nav = useNavigate();

  return (
    <AuthShell eyebrow={t("worker_welcome_eyebrow")} title={t("worker_welcome_title")} description={t("worker_welcome_body")}>
      <div className="rounded-2xl border border-outline-variant/10 bg-surface-container-lowest p-6 shadow-sm md:p-8 space-y-4">
        <button
          type="button"
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-6 py-4 text-sm font-bold text-on-primary shadow-sm transition-colors hover:bg-primary-dim"
          onClick={() => nav("/worker/signup")}
        >
          <MatIcon name="person_add" className="text-xl" />
          {t("worker_welcome_cta")}
        </button>
        <Link
          to="/login"
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-outline-variant/30 py-3 text-sm font-semibold text-primary hover:bg-surface-container-low"
        >
          <MatIcon name="login" className="text-lg" />
          {t("worker_welcome_have_account")}
        </Link>
      </div>
    </AuthShell>
  );
}
