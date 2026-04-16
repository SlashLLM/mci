import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Outlet } from "react-router-dom";
import { getRole } from "../../api";
import UnifiedPortalLayout from "../portal/UnifiedPortalLayout";

export function TaPortalLayout() {
  const { t } = useTranslation();
  const isAdmin = getRole() === "admin";

  useEffect(() => {
    document.title = `${t("job_orders")} | MCI Workforce`;
  }, [t]);

  return (
    <UnifiedPortalLayout
      role="ta"
      roleInitial="T"
      brandTitle={isAdmin ? "Admin" : t("ta_portal_brand_title")}
      brandSubtitleKey="ta_portal_subtitle"
      sideNav={
        isAdmin
          ? [
              { to: "/ta/workers", labelKey: "ta_nav_workers", icon: "badge", end: false },
              { to: "/ta/clients", labelKey: "ta_nav_clients", icon: "groups", end: false },
              { to: "/ta/talent-agents", labelKey: "TA", icon: "supervisor_account", end: false },
              { to: "/ta/reports", labelKey: "admin_reports_nav", icon: "report", end: false },
            ]
          : [
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
            ]
      }
      primaryCta={{ to: isAdmin ? "/ta/workers" : "/ta/new", label: isAdmin ? "Workers" : t("job_form_new") }}
      floatingCta={{ to: isAdmin ? "/ta/workers" : "/ta/new", ariaLabelKey: isAdmin ? "ta_nav_workers" : "job_form_new" }}
      asideCta={{ to: isAdmin ? "/ta/workers" : "/ta/new", labelKey: isAdmin ? "ta_nav_workers" : "job_form_new" }}
    >
      <Outlet />
    </UnifiedPortalLayout>
  );
}
