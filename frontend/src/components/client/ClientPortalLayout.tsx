import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Outlet } from "react-router-dom";
import UnifiedPortalLayout from "../portal/UnifiedPortalLayout";

export function ClientPortalLayout() {
  const { t } = useTranslation();

  useEffect(() => {
    document.title = `${t("job_orders")} | MCI Workforce`;
  }, [t]);

  return (
    <UnifiedPortalLayout
      role="client"
      roleInitial="C"
      brandTitle="Client portal"
      sideNav={[
        { to: "/client", labelKey: "job_orders", icon: "assignment", end: true },
        { to: "/client/new", labelKey: "job_form_new", icon: "add_circle" },
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
