import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Outlet } from "react-router-dom";
import UnifiedPortalLayout from "../portal/UnifiedPortalLayout";

export function TaPortalLayout() {
  const { t } = useTranslation();

  useEffect(() => {
    document.title = `${t("job_orders")} | MCI Workforce`;
  }, [t]);

  return (
    <UnifiedPortalLayout
      role="ta"
      roleInitial="T"
      brandTitle={t("ta_portal_brand_title")}
      brandSubtitleKey="ta_portal_subtitle"
      sideNav={[
        { to: "/ta", labelKey: "job_orders", icon: "assignment", end: true },
        { to: "/ta/messaging", labelKey: "messaging_nav", icon: "forum" },
        { to: "/ta/workers", labelKey: "ta_nav_workers", icon: "badge" },
        { to: "/ta/notifications", labelKey: "notifications_title", icon: "notifications" },
        { to: "/ta/profile", labelKey: "ta_nav_profile", icon: "person" },
        { to: "/ta/clients", labelKey: "ta_nav_clients", icon: "groups" },
        { to: "/ta/new", labelKey: "job_form_new", icon: "add_circle" },
        { to: "/ta/analytics", labelKey: "analytics", icon: "bar_chart" },
        { to: "/ta/exports", labelKey: "exports", icon: "download" },
        { to: "/ta/timesheets", labelKey: "ta_tab_timesheets", icon: "history_toggle_off" },
      ]}
      primaryCta={{ to: "/ta/new", label: t("job_form_new") }}
      floatingCta={{ to: "/ta/new", ariaLabelKey: "job_form_new" }}
      asideCta={{ to: "/ta/new", labelKey: "job_form_new" }}
    >
      <Outlet />
    </UnifiedPortalLayout>
  );
}
