import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { UberLinkButton } from "../ui/UberPrimitives";

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
    <div className="flex min-h-screen flex-col overflow-x-hidden bg-white font-body text-black">
      <header className="sticky top-0 z-50 flex h-16 w-full shrink-0 items-center justify-between border-b border-black/10 bg-white px-4 md:px-8">
        <Link
          to="/"
          className="flex min-w-0 items-center gap-2 text-xl font-bold tracking-tight text-black"
        >
          <MatIcon name="badge" className="text-2xl text-black" />
          <span className="truncate">{t("app_title")}</span>
        </Link>
        <div className="flex shrink-0 items-center gap-2">
          <Link to="/login" className="hidden rounded-pill bg-[#efefef] px-4 py-2 text-sm font-medium text-black sm:inline-flex">
            {t("login")}
          </Link>
          <UberLinkButton to="/worker/signup" className="hidden sm:inline-flex">{t("home_cta_register")}</UberLinkButton>
          <label className="sr-only">{t("language")}</label>
          <select
            className="max-w-[5.5rem] rounded-pill border border-black px-3 py-1.5 text-xs text-black"
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

      <footer className="mt-auto w-full shrink-0 bg-black py-8 text-xs tracking-wide text-white">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-8 md:flex-row">
          <div>
            <span className="mr-2 font-manrope font-bold text-white">{t("app_title")}</span>
            <span className="text-[#afafaf]">© {new Date().getFullYear()}</span>
          </div>
          <nav className="flex flex-wrap justify-center gap-6 text-[#afafaf]">
            <span>{t("auth_footer_hint")}</span>
          </nav>
        </div>
      </footer>
    </div>
  );
}
