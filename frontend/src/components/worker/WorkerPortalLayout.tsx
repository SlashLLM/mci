import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { clearSession } from "../../api";

function MatIcon({ name, className = "" }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`.trim()}>{name}</span>;
}

const sidebarInactive =
  "flex items-center gap-3 text-slate-500 hover:text-primary px-6 py-3 hover:translate-x-1 transition-transform rounded-l-xl";
const sidebarActive =
  "flex items-center gap-3 bg-white text-primary rounded-l-xl ml-4 shadow-sm px-4 py-3 hover:translate-x-1 transition-transform";

function SideNavLink({ to, end, icon, children }: { to: string; end?: boolean; icon: string; children: ReactNode }) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => (isActive ? sidebarActive : sidebarInactive)}>
      <MatIcon name={icon} />
      {children}
    </NavLink>
  );
}

export default function WorkerPortalLayout({ children }: { children: ReactNode }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  const topLink = "text-slate-600 hover:text-primary transition-colors";
  const topActive = "text-primary border-b-2 border-primary font-semibold pb-0.5";

  return (
    <div className="min-h-screen bg-background text-on-background font-body overflow-x-hidden">
      <header className="fixed top-0 left-0 right-0 z-50 flex h-16 w-full items-center justify-between bg-slate-50 px-4 font-manrope antialiased shadow-sm shadow-slate-200/50 md:px-8">
        <div className="flex min-w-0 flex-1 items-center gap-4 md:gap-8">
          <button
            type="button"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-slate-600 hover:bg-slate-200/50 md:hidden"
            aria-label="Open menu"
            onClick={() => setMenuOpen(true)}
          >
            <MatIcon name="menu" className="text-2xl" />
          </button>
          <span className="truncate text-xl font-bold tracking-tight text-blue-900">MCI Workforce</span>
          <nav className="ml-2 hidden items-center gap-6 md:flex">
            <NavLink className={({ isActive }) => `${topLink} ${isActive ? topActive : ""}`} to="/worker/marketplace">
              {t("marketplace")}
            </NavLink>
            <NavLink className={({ isActive }) => `${topLink} ${isActive ? topActive : ""}`} to="/worker" end>
              {t("my_offers")}
            </NavLink>
            <NavLink className={({ isActive }) => `${topLink} ${isActive ? topActive : ""}`} to="/worker/shifts">
              {t("my_shifts")}
            </NavLink>
            <NavLink className={({ isActive }) => `${topLink} ${isActive ? topActive : ""}`} to="/worker/history">
              {t("worker_history_title")}
            </NavLink>
          </nav>
        </div>
        <div className="flex shrink-0 items-center gap-2 md:gap-4">
          <label className="sr-only">{t("language")}</label>
          <select
            className="max-w-[5.5rem] rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-2 py-1.5 text-xs text-on-surface"
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
          <button
            type="button"
            className="hidden rounded-full p-2 text-slate-600 transition-colors hover:bg-slate-200/50 active:scale-95 sm:block"
            aria-label="Notifications"
          >
            <MatIcon name="notifications" />
          </button>
          <NavLink
            to="/worker/clock"
            className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary shadow-sm transition-colors hover:bg-primary-dim active:scale-95 md:px-6"
          >
            Clock In
          </NavLink>
          <div className="ml-1 hidden h-10 w-10 overflow-hidden rounded-full border-2 border-surface-container sm:block">
            <div className="flex h-full w-full items-center justify-center bg-primary-container text-sm font-bold text-on-primary-container">
              W
            </div>
          </div>
        </div>
      </header>

      {menuOpen && (
        <button type="button" className="fixed inset-0 z-40 bg-black/40 md:hidden" aria-label="Close menu" onClick={() => setMenuOpen(false)} />
      )}
      <aside
        className={`fixed left-0 top-0 z-40 flex h-screen w-64 flex-col bg-slate-100 pt-20 font-manrope text-sm font-medium transition-transform duration-200 md:translate-x-0 ${
          menuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="mb-8 px-6">
          <h2 className="text-xl font-black text-blue-900">Workforce Portal</h2>
          <p className="text-[10px] uppercase tracking-widest text-on-surface-variant opacity-70">Editorial Ledger v1.0</p>
        </div>
        <nav className="flex flex-1 flex-col space-y-1">
          <SideNavLink to="/worker/marketplace" icon="storefront">
            {t("marketplace")}
          </SideNavLink>
          <SideNavLink to="/worker" end icon="local_offer">
            {t("my_offers")}
          </SideNavLink>
          <SideNavLink to="/worker/shifts" icon="event_available">
            {t("my_shifts")}
          </SideNavLink>
          <SideNavLink to="/worker/history" icon="history">
            {t("worker_history_title")}
          </SideNavLink>
          <SideNavLink to="/worker/earnings" icon="payments">
            Earnings
          </SideNavLink>
          <SideNavLink to="/worker/profile" icon="person_outline">
            {t("profile")}
          </SideNavLink>
          <SideNavLink to="/worker/settings" icon="settings">
            {t("settings")}
          </SideNavLink>
          <SideNavLink to="/worker/clock" icon="schedule">
            Clock
          </SideNavLink>
        </nav>
        <div className="border-t border-slate-200/80 px-6 py-6">
          <NavLink
            to="/worker/marketplace"
            className="mb-4 flex w-full items-center justify-center gap-2 rounded-xl bg-primary-container py-3 font-bold text-on-primary-container transition-all hover:brightness-95"
          >
            New Shift Available
          </NavLink>
          <div className="space-y-1">
            <button
              type="button"
              className="flex w-full items-center gap-3 py-2 text-slate-400 transition-colors hover:text-primary"
              onClick={() => {
                clearSession();
                navigate("/login");
              }}
            >
              <MatIcon name="logout" />
              Log out
            </button>
          </div>
        </div>
      </aside>

      <main className="min-h-screen pt-20 md:pl-64">
        {children}
        <footer className="mt-auto w-full border-t border-slate-200/80 bg-slate-50 py-8 font-body text-xs tracking-wide">
          <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-8 opacity-80 transition-opacity hover:opacity-100 md:flex-row">
            <div>
              <span className="mr-4 font-manrope font-bold text-slate-600">MCI Workforce</span>
              <span className="text-slate-500">© {new Date().getFullYear()} MCI Workforce Management. All rights reserved.</span>
            </div>
            <nav className="flex flex-wrap justify-center gap-6">
              <a className="text-slate-500 underline underline-offset-4 hover:text-primary" href="#">
                Privacy Policy
              </a>
              <a className="text-slate-500 underline underline-offset-4 hover:text-primary" href="#">
                Terms of Service
              </a>
              <a className="text-slate-500 underline underline-offset-4 hover:text-primary" href="#">
                Compliance
              </a>
              <a className="text-slate-500 underline underline-offset-4 hover:text-primary" href="#">
                Support
              </a>
            </nav>
          </div>
        </footer>
      </main>

      <NavLink
        to="/worker/marketplace"
        className="fixed bottom-8 right-8 z-50 flex h-16 w-16 items-center justify-center rounded-full bg-primary text-on-primary shadow-2xl transition-all hover:scale-110 active:scale-95"
        aria-label={t("marketplace")}
      >
        <MatIcon name="add" className="text-3xl" />
      </NavLink>
    </div>
  );
}
