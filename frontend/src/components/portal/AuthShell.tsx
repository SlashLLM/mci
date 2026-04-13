import type { ReactNode } from "react";
import PublicSiteLayout from "./PublicSiteLayout";

type AuthShellProps = {
  children: ReactNode;
  eyebrow?: string;
  title: string;
  description?: string;
  /** Marketing-style pages: no eyebrow/title block above children */
  omitHero?: boolean;
};

/**
 * Public auth pages (login, worker signup): same chrome as the main site, narrow content column.
 */
export default function AuthShell({ children, eyebrow, title, description, omitHero }: AuthShellProps) {
  return (
    <PublicSiteLayout mainClassName="max-w-lg">
      {!omitHero ? (
        <header className="mb-8 space-y-2">
          {eyebrow ? (
            <span className="text-xs font-bold uppercase tracking-[0.2em] text-black">{eyebrow}</span>
          ) : null}
          <h1 className="font-headline text-3xl font-extrabold tracking-tight text-black md:text-4xl">{title}</h1>
          {description ? <p className="max-w-md text-sm leading-relaxed text-[#4b4b4b]">{description}</p> : null}
        </header>
      ) : null}
      {children}
    </PublicSiteLayout>
  );
}
