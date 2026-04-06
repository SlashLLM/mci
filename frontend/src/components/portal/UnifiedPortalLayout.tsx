import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { clearSession } from "../../api";

function MatIcon({ name, className = "" }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`.trim()} aria-hidden>{name}</span>;
}

type SideItem = {
  to: string;
  labelKey: string;
  icon: string;
  end?: boolean;
};

type UnifiedPortalLayoutProps = {
  role: "worker" | "client" | "ta";
  roleInitial: string;
  brandTitle: string;
  brandSubtitleKey?: string;
  sideNav: SideItem[];

  primaryCta: {
    to: string;
    /** Used for role=worker where the clock page must preserve `?assignment=` query. */
    getHref?: (pathname: string, search: string) => string;
    label: string;
  };

  floatingCta: {
    to: string;
    ariaLabelKey: string;
  };

  asideCta: {
    to: string;
    labelKey: string;
  };

  children: ReactNode;
};

const sidebarInactive =
  "w-full flex items-center gap-3 text-slate-500 hover:text-primary px-6 py-3 rounded-l-xl";
const sidebarActive =
  "w-full flex items-center gap-3 bg-white text-primary rounded-l-xl shadow-sm px-4 py-3";

function SideNavLink({
  to,
  end,
  icon,
  children,
  collapsed,
}: {
  to: string;
  end?: boolean;
  icon: string;
  children: ReactNode;
  collapsed: boolean;
}) {
  const inactiveClass = collapsed
    ? `${sidebarInactive} md:justify-center md:gap-0 md:px-0 md:rounded-none`
    : sidebarInactive;
  const activeClass = collapsed
    ? `${sidebarActive} md:justify-center md:gap-0 md:px-0 md:rounded-none`
    : sidebarActive;

  return (
    <NavLink to={to} end={end} className={({ isActive }) => (isActive ? activeClass : inactiveClass)}>
      <MatIcon name={icon} />
      <span className={collapsed ? "md:hidden" : ""}>{children}</span>
    </NavLink>
  );
}

export default function UnifiedPortalLayout({
  role: _role,
  roleInitial,
  brandTitle,
  brandSubtitleKey,
  sideNav,
  primaryCta,
  floatingCta,
  asideCta,
  children,
}: UnifiedPortalLayoutProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const primaryHref = useMemo(() => {
    if (primaryCta.getHref) return primaryCta.getHref(location.pathname, location.search);
    return primaryCta.to;
  }, [location.pathname, location.search, primaryCta]);

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  const sidebarSubtitle = brandSubtitleKey ? t(brandSubtitleKey) : "";
  const asideWidthClass = sidebarCollapsed ? "md:w-20" : "md:w-64";
  const mainPaddingLeftClass = sidebarCollapsed ? "md:pl-[6rem]" : "md:pl-[17rem]";

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
            to={primaryHref}
            className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary shadow-sm transition-colors hover:bg-primary-dim active:scale-95 md:px-6"
          >
            {primaryCta.label}
          </NavLink>
          <div className="ml-1 hidden h-10 w-10 overflow-hidden rounded-full border-2 border-surface-container sm:block">
            <div className="flex h-full w-full items-center justify-center bg-primary-container text-sm font-bold text-on-primary-container">
              {roleInitial}
            </div>
          </div>
        </div>
      </header>

      {menuOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          aria-label="Close menu"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <aside
        className={`fixed left-0 top-0 z-40 flex h-screen w-64 flex-col bg-slate-100 pt-20 font-manrope text-sm font-medium transition-all duration-200 ${asideWidthClass} border-r border-slate-200/80 md:translate-x-0 ${
          menuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="mb-8 flex items-start justify-between gap-3 px-6 md:px-4">
          <div className="min-w-0">
            <h2 className={`text-xl font-black text-blue-900 ${sidebarCollapsed ? "md:hidden" : ""}`}>{brandTitle}</h2>
          {brandSubtitleKey && (
            <p className={`text-[10px] uppercase tracking-widest text-on-surface-variant opacity-70 ${sidebarCollapsed ? "md:hidden" : ""}`}>
              {sidebarSubtitle}
            </p>
          )}
          </div>

          <button
            type="button"
            className="hidden h-9 w-9 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-200/50 active:scale-95 md:flex"
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => setSidebarCollapsed((v) => !v)}
          >
            <MatIcon name={sidebarCollapsed ? "chevron_right" : "chevron_left"} />
          </button>
        </div>
        <nav className="flex flex-1 flex-col space-y-1 overflow-y-auto">
          {sideNav.map((item) => (
            <SideNavLink key={item.to} to={item.to} end={item.end} icon={item.icon} collapsed={sidebarCollapsed}>
              {t(item.labelKey)}
            </SideNavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200/80 px-6 py-6 md:px-3">
          <NavLink
            to={asideCta.to}
            className="mb-4 flex w-full items-center justify-center gap-2 rounded-xl bg-primary-container py-3 font-bold text-on-primary-container transition-all hover:brightness-95"
          >
            <MatIcon name="add_circle" className="text-lg" />
            <span className={sidebarCollapsed ? "md:hidden" : ""}>{t(asideCta.labelKey)}</span>
          </NavLink>
          <div className="space-y-1">
            <button
              type="button"
              className="flex w-full items-center gap-3 py-2 text-slate-400 transition-colors hover:text-primary md:gap-0 md:justify-center"
              onClick={() => {
                clearSession();
                navigate("/");
              }}
            >
              <MatIcon name="logout" />
              <span className={sidebarCollapsed ? "md:hidden" : ""}>Log out</span>
            </button>
          </div>
        </div>
      </aside>

      <main className={`min-h-screen pt-20 transition-all duration-200 ${mainPaddingLeftClass}`}>
        {children}
        <footer className="mt-auto w-full border-t border-slate-200/80 bg-slate-50 py-8 font-body text-xs tracking-wide">
          <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-8 opacity-80 transition-opacity hover:opacity-100 md:flex-row">
            <div>
              <span className="mr-4 font-manrope font-bold text-slate-600">MCI Workforce</span>
              <span className="text-slate-500">© {new Date().getFullYear()} MCI Workforce Management. All rights reserved.</span>
            </div>
            <nav className="flex flex-wrap justify-center gap-6">
              <a className="text-slate-500 underline underline-offset-4 hover:text-primary" href="#" onClick={(e) => e.preventDefault()}>
                Privacy Policy
              </a>
              <a className="text-slate-500 underline underline-offset-4 hover:text-primary" href="#" onClick={(e) => e.preventDefault()}>
                Terms of Service
              </a>
              <a className="text-slate-500 underline underline-offset-4 hover:text-primary" href="#" onClick={(e) => e.preventDefault()}>
                Compliance
              </a>
              <a className="text-slate-500 underline underline-offset-4 hover:text-primary" href="#" onClick={(e) => e.preventDefault()}>
                Support
              </a>
            </nav>
          </div>
        </footer>
      </main>

      <NavLink
        to={floatingCta.to}
        className="fixed bottom-8 right-8 z-50 flex h-16 w-16 items-center justify-center rounded-full bg-primary text-on-primary shadow-2xl transition-all hover:scale-110 active:scale-95"
        aria-label={t(floatingCta.ariaLabelKey)}
      >
        <MatIcon name="add" className="text-3xl" />
      </NavLink>
    </div>
  );
}

