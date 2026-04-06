import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

export function TabPill({ to, end, children }: { to: string; end?: boolean; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end={end}
      relative="route"
      preventScrollReset
      className={({ isActive }) =>
        [
          "px-6 py-2.5 rounded-xl text-sm font-bold whitespace-nowrap transition-colors shrink-0",
          isActive
            ? "bg-surface-container-lowest text-primary shadow-sm"
            : "font-medium text-on-surface-variant hover:text-on-surface",
        ].join(" ")
      }
    >
      {children}
    </NavLink>
  );
}

export function TaTabPills() {
  const { t } = useTranslation();
  return (
    <>
      <TabPill to="." end>
        {t("job_orders")}
      </TabPill>
      <TabPill to="new">{t("job_form_new")}</TabPill>
      <TabPill to="analytics">{t("analytics")}</TabPill>
      <TabPill to="exports">{t("exports")}</TabPill>
      <TabPill to="timesheets">{t("ta_tab_timesheets")}</TabPill>
    </>
  );
}

/** Desktop-only pill row — place below page header to match mockup (header → tabs → body). */
export function TaDesktopTabStrip({ className = "" }: { className?: string }) {
  return (
    <div className={`max-md:hidden mb-8 overflow-x-auto no-scrollbar ${className}`}>
      <div className="flex flex-wrap items-center gap-1 bg-surface-container p-1 rounded-2xl w-fit max-w-full">
        <TaTabPills />
      </div>
    </div>
  );
}
