import { useTranslation } from "react-i18next";
import PublicSiteLayout from "../components/portal/PublicSiteLayout";
import { UberCard, UberLinkButton, UberSection } from "../components/ui/UberPrimitives";

function MatIcon({ name, className = "" }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`.trim()} aria-hidden>{name}</span>;
}

export default function HomePage() {
  const { t } = useTranslation();

  const featureCards = [
    { icon: "calendar_month", titleKey: "home_feature_shifts_title", bodyKey: "home_feature_shifts_body" },
    { icon: "verified_user", titleKey: "home_feature_compliance_title", bodyKey: "home_feature_compliance_body" },
    { icon: "payments", titleKey: "home_feature_pay_title", bodyKey: "home_feature_pay_body" },
    { icon: "groups", titleKey: "home_feature_roles_title", bodyKey: "home_feature_roles_body" },
  ] as const;

  const audiences = [
    { icon: "engineering", titleKey: "home_for_workers_title", bodyKey: "home_for_workers_body", to: "/worker/signup", ctaKey: "home_cta_register" },
    { icon: "business", titleKey: "home_for_clients_title", bodyKey: "home_for_clients_body", to: "/login", ctaKey: "home_cta_client_login" },
    { icon: "admin_panel_settings", titleKey: "home_for_ta_title", bodyKey: "home_for_ta_body", to: "/login", ctaKey: "home_cta_ta_login" },
  ] as const;

  return (
    <PublicSiteLayout mainClassName="max-w-[1136px]">
      <UberSection className="mb-14 px-0 md:mb-20">
        <p className="mb-3 text-xs font-bold uppercase tracking-[0.2em] text-black">{t("home_hero_eyebrow")}</p>
        <h1 className="font-headline text-4xl font-extrabold tracking-tight text-black md:text-5xl lg:text-6xl">
          {t("home_hero_title")}
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-[#4b4b4b] md:text-xl">{t("home_hero_subtitle")}</p>
      </UberSection>

      <UberSection className="mb-16 px-0 md:mb-24">
        <h2 className="font-headline text-2xl font-extrabold text-black md:text-3xl">{t("home_about_title")}</h2>
        <p className="mt-4 max-w-3xl text-base leading-relaxed text-[#4b4b4b] md:text-lg">{t("home_about_body")}</p>
      </UberSection>

      <UberSection className="mb-16 px-0 md:mb-24">
        <h2 className="font-headline text-2xl font-extrabold text-black md:text-3xl">{t("home_features_title")}</h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {featureCards.map((f) => (
            <UberCard key={f.titleKey} className="transition-shadow hover:shadow-medium">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-card bg-[#efefef] text-black">
                <MatIcon name={f.icon} className="text-2xl" />
              </div>
              <h3 className="font-headline text-lg font-bold text-black">{t(f.titleKey)}</h3>
              <p className="mt-2 text-sm leading-relaxed text-[#4b4b4b]">{t(f.bodyKey)}</p>
            </UberCard>
          ))}
        </div>
      </UberSection>

      <UberSection className="mb-8 px-0">
        <h2 className="font-headline text-2xl font-extrabold text-black md:text-3xl">{t("home_audiences_title")}</h2>
        <div className="mt-10 grid gap-8 lg:grid-cols-3">
          {audiences.map((a) => (
            <UberCard key={a.titleKey} featured className="flex flex-col">
              <MatIcon name={a.icon} className="mb-4 text-4xl text-black" />
              <h3 className="font-headline text-xl font-bold text-black">{t(a.titleKey)}</h3>
              <p className="mt-3 flex-1 text-sm leading-relaxed text-[#4b4b4b]">{t(a.bodyKey)}</p>
              <UberLinkButton to={a.to} className="mt-6 text-center font-bold">
                {t(a.ctaKey)}
              </UberLinkButton>
            </UberCard>
          ))}
        </div>
      </UberSection>
    </PublicSiteLayout>
  );
}
