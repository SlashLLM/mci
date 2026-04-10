import { useTranslation } from "react-i18next";
import PortalAnalyticsDashboard from "../../components/analytics/PortalAnalyticsDashboard";

export function TaAnalyticsPage() {
  const { t } = useTranslation();
  return (
    <PortalAnalyticsDashboard
      role="ta"
      title={t("analytics")}
      subtitle={t("ta_analytics_intro")}
    />
  );
}
