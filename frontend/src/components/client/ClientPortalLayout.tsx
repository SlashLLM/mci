import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearSession, getToken } from "../../api";

const icon = "material-symbols-outlined text-[20px] shrink-0";

function SideNavLink({
  to,
  end,
  symbol,
  children,
}: {
  to: string;
  end?: boolean;
  symbol: string;
  children: React.ReactNode;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      relative="route"
      className={({ isActive }) =>
        [
          "px-6 py-3 flex items-center gap-3 transition-transform ease-in-out duration-300 rounded-l-xl ml-4",
          isActive
            ? "bg-white dark:bg-slate-800 text-blue-700 dark:text-blue-300 shadow-sm"
            : "text-slate-500 dark:text-slate-500 hover:text-blue-600 dark:hover:text-blue-400 hover:translate-x-1",
        ].join(" ")
      }
    >
      <span className={icon} aria-hidden>
        {symbol}
      </span>
      {children}
    </NavLink>
  );
}

function TabPill({ to, end, children }: { to: string; end?: boolean; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end={end}
      relative="route"
      preventScrollReset
      className={({ isActive }) =>
        [
          "px-6 py-2.5 rounded-xl text-sm font-bold whitespace-nowrap transition-colors",
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

function LangAndLogout({ className }: { className?: string }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  return (
    <div className={className}>
      <label className="sr-only">{t("language")}</label>
      <select
        className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 text-xs text-on-background"
        value={i18n.language.startsWith("zh") ? "zh" : "en"}
        onChange={(e) => {
          const lng = e.target.value;
          i18n.changeLanguage(lng);
          localStorage.setItem("locale", lng);
        }}
      >
        <option value="en">EN</option>
        <option value="zh">中文</option>
      </select>
      {getToken() && (
        <button
          type="button"
          className="text-xs font-semibold text-slate-600 dark:text-slate-300 hover:text-primary px-2"
          onClick={() => {
            clearSession();
            navigate("/login");
          }}
        >
          Log out
        </button>
      )}
    </div>
  );
}

/** Sidebar + footer shell (no top bar — nav lives in sidebar only on desktop). */
export function ClientPortalLayout() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = `${t("job_orders")} | MCI Workforce`;
  }, [t]);

  return (
    <div className="bg-background font-body text-on-background antialiased overflow-x-hidden min-h-screen">
      <aside className="h-screen w-64 fixed left-0 top-0 pt-6 bg-slate-100 dark:bg-slate-950 flex-col border-r border-slate-200/50 dark:border-slate-800 font-manrope text-sm font-medium z-40 hidden md:flex">
        <div className="px-6 mb-6 flex items-center gap-3">
          <button type="button" onClick={() => navigate("/client")} className="flex items-center gap-3 text-left min-w-0">
            <div className="w-10 h-10 bg-primary-container rounded-lg flex items-center justify-center text-primary shrink-0">
              <span className={icon}>grid_view</span>
            </div>
            <div className="min-w-0">
              <h2 className="font-black text-blue-900 dark:text-blue-50 leading-tight truncate">MCI Workforce</h2>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest">Client portal</p>
            </div>
          </button>
        </div>
        <div className="px-6 mb-6">
          <LangAndLogout className="flex flex-wrap items-center gap-2" />
        </div>
        <nav className="flex-1 space-y-1">
          <SideNavLink to="." end symbol="assignment">
            {t("job_orders")}
          </SideNavLink>
          <SideNavLink to="new" symbol="add_circle">
            {t("job_form_new")}
          </SideNavLink>
          <SideNavLink to="timesheets" symbol="history_toggle_off">
            {t("timesheets")}
          </SideNavLink>
          <SideNavLink to="live" symbol="sensors">
            {t("live_attendance")}
          </SideNavLink>
        </nav>
        <div className="px-6 py-6">
          <div className="bg-primary-container p-4 rounded-xl">
            <p className="text-on-primary-container text-xs font-bold mb-2">{t("client_portal_tip_title")}</p>
            <p className="text-on-primary-container/80 text-[11px] leading-tight">{t("client_portal_tip_body")}</p>
          </div>
        </div>
        <div className="mt-auto border-t border-slate-200/50 dark:border-slate-800/50 py-4">
          <a
            className="text-slate-500 px-6 py-2 flex items-center gap-3 hover:text-blue-600 hover:translate-x-1 transition-transform"
            href="#"
            onClick={(e) => e.preventDefault()}
          >
            <span className={icon}>settings</span>
            Settings
          </a>
          <a
            className="text-slate-500 px-6 py-2 flex items-center gap-3 hover:text-blue-600 hover:translate-x-1 transition-transform"
            href="#"
            onClick={(e) => e.preventDefault()}
          >
            <span className={icon}>help_outline</span>
            Help
          </a>
        </div>
      </aside>

      <main className="md:ml-64 min-h-screen bg-surface-container-low transition-all duration-300">
        <div className="md:hidden sticky top-0 z-30 bg-surface-container-low/95 backdrop-blur border-b border-slate-200/60">
          <div className="flex justify-between items-center gap-2 px-3 py-2 border-b border-slate-200/40">
            <button
              type="button"
              onClick={() => navigate("/client")}
              className="text-sm font-bold text-blue-900 dark:text-blue-100 truncate"
            >
              MCI Workforce
            </button>
            <LangAndLogout className="flex items-center gap-1 shrink-0" />
          </div>
          <div className="px-3 py-2 overflow-x-auto no-scrollbar">
            <div className="flex gap-2 min-w-max">
              <TabPill to="." end>
                {t("job_orders")}
              </TabPill>
              <TabPill to="new">{t("job_form_new")}</TabPill>
              <TabPill to="timesheets">{t("timesheets")}</TabPill>
              <TabPill to="live">{t("live_attendance")}</TabPill>
            </div>
          </div>
        </div>
        <div className="max-w-7xl mx-auto px-4 md:px-8 py-8 md:py-10">
          <Outlet />
        </div>
      </main>

      <footer className="md:ml-64 bg-slate-50 dark:bg-slate-900 w-full py-8 border-t border-slate-200/10">
        <div className="flex flex-col md:flex-row justify-between items-center px-8 max-w-7xl mx-auto font-body text-xs tracking-wide gap-4 text-slate-400">
          <span className="font-manrope font-bold text-slate-500">MCI Workforce Management</span>
          <div className="flex flex-wrap gap-6 justify-center">
            <a className="hover:text-primary underline underline-offset-4 opacity-80" href="#" onClick={(e) => e.preventDefault()}>
              Privacy
            </a>
            <a className="hover:text-primary underline underline-offset-4 opacity-80" href="#" onClick={(e) => e.preventDefault()}>
              Terms
            </a>
            <a className="hover:text-primary underline underline-offset-4 opacity-80" href="#" onClick={(e) => e.preventDefault()}>
              Support
            </a>
          </div>
          <p>© {new Date().getFullYear()} MCI Workforce</p>
        </div>
      </footer>
    </div>
  );
}
