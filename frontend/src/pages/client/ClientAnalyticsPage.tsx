import { useTranslation } from "react-i18next";
import PortalAnalyticsDashboard from "../../components/analytics/PortalAnalyticsDashboard";

export function ClientAnalyticsPage() {
  const { t } = useTranslation();
  return (
    <PortalAnalyticsDashboard
      role="client"
      title={t("analytics")}
      subtitle={t("client_analytics_intro")}
    />
  );
}
