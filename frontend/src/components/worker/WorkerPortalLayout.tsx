import type { ReactNode } from "react";
import UnifiedPortalLayout from "../portal/UnifiedPortalLayout";

export default function WorkerPortalLayout({ children }: { children: ReactNode }) {
  return (
    <UnifiedPortalLayout
      role="worker"
      roleInitial="W"
      brandTitle="Workforce Portal"
      brandSubtitleKey="Editorial Ledger v1.0"
      sideNav={[
        { to: "/worker/marketplace", labelKey: "marketplace", icon: "storefront" },
        { to: "/worker/shifts", labelKey: "my_shifts", icon: "event_available" },
        { to: "/worker/history", labelKey: "worker_history_title", icon: "history" },
        { to: "/worker/earnings", labelKey: "worker_earnings_nav", icon: "payments" },
        { to: "/worker/profile", labelKey: "profile", icon: "person_outline" },
      ]}
      primaryCta={{
        to: "/worker/clock",
        getHref: (pathname, search) => (pathname === "/worker/clock" ? `/worker/clock${search}` : "/worker/clock"),
        label: "Clock In",
      }}
      floatingCta={{ to: "/worker/marketplace", ariaLabelKey: "marketplace" }}
      asideCta={{ to: "/worker/marketplace", labelKey: "New Shift Available" }}
    >
      {children}
    </UnifiedPortalLayout>
  );
}
