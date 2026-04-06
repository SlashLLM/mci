import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

function MatIcon({ name, className = "" }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`.trim()} aria-hidden>{name}</span>;
}

type PublicSiteLayoutProps = {
  children: ReactNode;
  /** Tailwind max-width + width classes for main, e.g. max-w-lg or max-w-7xl */
  mainClassName?: string;
};

/**
 * Shared chrome for public pages (home, login, signup): header, footer, portal-aligned styling.
 */
export default function PublicSiteLayout({ children, mainClassName = "max-w-lg" }: PublicSiteLayoutProps) {
  const { t, i18n } = useTranslation();

  return (
    <div className="min-h-screen bg-background text-on-background font-body overflow-x-hidden flex flex-col">
      <header className="sticky top-0 z-50 flex h-16 w-full shrink-0 items-center justify-between border-b border-slate-200/80 bg-slate-50 px-4 font-manrope antialiased shadow-sm shadow-slate-200/50 md:px-8">
        <Link
          to="/"
          className="flex min-w-0 items-center gap-2 text-xl font-bold tracking-tight text-blue-900 hover:text-primary-dim"
        >
          <MatIcon name="badge" className="text-2xl text-primary" />
          <span className="truncate">{t("app_title")}</span>
        </Link>
        <div className="flex shrink-0 items-center gap-2 md:gap-3">
          <Link
            to="/login"
            className="hidden rounded-lg px-3 py-2 text-sm font-semibold text-on-surface-variant hover:text-primary sm:inline"
          >
            {t("login")}
          </Link>
          <Link
            to="/worker/signup"
            className="hidden rounded-xl border border-primary/30 bg-primary-container/50 px-3 py-2 text-sm font-bold text-on-primary-container hover:bg-primary-container sm:inline"
          >
            {t("home_cta_register")}
          </Link>
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
        </div>
      </header>

      <main className={`mx-auto w-full flex-1 px-4 py-10 md:px-8 md:py-14 ${mainClassName}`}>{children}</main>

      <footer className="mt-auto w-full shrink-0 border-t border-slate-200/80 bg-slate-50 py-8 font-body text-xs tracking-wide">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-8 opacity-90 md:flex-row">
          <div>
            <span className="mr-2 font-manrope font-bold text-slate-600">{t("app_title")}</span>
            <span className="text-slate-500">© {new Date().getFullYear()}</span>
          </div>
          <nav className="flex flex-wrap justify-center gap-6 text-slate-500">
            <span>{t("auth_footer_hint")}</span>
          </nav>
        </div>
      </footer>
    </div>
  );
}
