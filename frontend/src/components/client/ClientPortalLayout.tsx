import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Outlet, useLocation } from "react-router-dom";
import { api } from "../../api";
import UnifiedPortalLayout from "../portal/UnifiedPortalLayout";

export function ClientPortalLayout() {
  const { t } = useTranslation();
  const location = useLocation();
  const [companyName, setCompanyName] = useState<string | null>(null);

  useEffect(() => {
    void api<{ company_name: string }>("/client/me/profile")
      .then((p) => {
        const n = (p.company_name || "").trim();
        setCompanyName(n || null);
      })
      .catch(() => setCompanyName(null));
  }, [location.pathname]);

  const brandTitle = companyName ?? "Client portal";
  const roleInitial = useMemo(() => {
    if (!companyName) return "C";
    const ch = [...companyName][0];
    return ch ? ch.toLocaleUpperCase() : "C";
  }, [companyName]);

  useEffect(() => {
    document.title = `${t("job_orders")} | MCI Workforce`;
  }, [t]);

  return (
    <UnifiedPortalLayout
      role="client"
      roleInitial={roleInitial}
      brandTitle={brandTitle}
      sideNav={[
        { to: "/client", labelKey: "job_orders", icon: "assignment", end: true },
        { to: "/client/messaging", labelKey: "messaging_nav", icon: "forum" },
        { to: "/client/analytics", labelKey: "analytics", icon: "bar_chart" },
        { to: "/client/profile", labelKey: "profile", icon: "person_outline" },
        { to: "/client/job-history", labelKey: "client_job_history_heading", icon: "inventory_2" },
        { to: "/client/new", labelKey: "job_form_new", icon: "add_circle" },
        { to: "/client/notifications", labelKey: "notifications_title", icon: "notifications" },
        { to: "/client/timesheets", labelKey: "timesheets", icon: "history_toggle_off" },
        { to: "/client/ta-contract", labelKey: "client_nav_ta_contract", icon: "handshake" },
        { to: "/client/live", labelKey: "live_attendance", icon: "sensors" },
      ]}
      primaryCta={{ to: "/client/new", label: t("job_form_new") }}
      floatingCta={{ to: "/client/new", ariaLabelKey: "job_form_new" }}
      asideCta={{ to: "/client/new", labelKey: "job_form_new" }}
    >
      <Outlet />
    </UnifiedPortalLayout>
  );
}
