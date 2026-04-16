import { useTranslation } from "react-i18next";
import { getRole } from "../../api";
import PortalAnalyticsDashboard from "../../components/analytics/PortalAnalyticsDashboard";

export function TaAnalyticsPage() {
  const { t } = useTranslation();
  const isAdmin = getRole() === "admin";
  return (
    <PortalAnalyticsDashboard
      role={isAdmin ? "admin" : "ta"}
      title={t("analytics")}
      subtitle={t(isAdmin ? "admin_analytics_intro" : "ta_analytics_intro")}
    />
  );
}
