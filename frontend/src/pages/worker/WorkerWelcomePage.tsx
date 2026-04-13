import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import AuthShell from "../../components/portal/AuthShell";
import { UberButton } from "../../components/ui/UberPrimitives";

function MatIcon({ name, className = "" }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`.trim()} aria-hidden>{name}</span>;
}

export default function WorkerWelcomePage() {
  const { t } = useTranslation();
  const nav = useNavigate();

  return (
    <AuthShell eyebrow={t("worker_welcome_eyebrow")} title={t("worker_welcome_title")} description={t("worker_welcome_body")}>
      <div className="space-y-4 rounded-featured border border-black/10 bg-white p-6 shadow-card md:p-8">
        <UberButton className="flex w-full items-center justify-center gap-2 py-4 text-sm font-bold" onClick={() => nav("/worker/signup")}>
          <MatIcon name="person_add" className="text-xl" />
          {t("worker_welcome_cta")}
        </UberButton>
        <Link
          to="/login"
          className="flex w-full items-center justify-center gap-2 rounded-pill border border-black py-3 text-sm font-semibold text-black hover:bg-[#efefef]"
        >
          <MatIcon name="login" className="text-lg" />
          {t("worker_welcome_have_account")}
        </Link>
      </div>
    </AuthShell>
  );
}
