import type { InputHTMLAttributes, ReactNode } from "react";
import { NavLink } from "react-router-dom";

type ButtonVariant = "primary" | "secondary" | "chip" | "floating";

export function UberButton({
  children,
  className = "",
  variant = "primary",
  type = "button",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  const variantClass =
    variant === "primary"
      ? "bg-black text-white hover:bg-black/90"
      : variant === "secondary"
        ? "bg-white text-black hover:bg-[#e2e2e2]"
        : variant === "chip"
          ? "bg-[#efefef] text-black hover:shadow-pressed"
          : "bg-white text-black shadow-floating hover:bg-[#f3f3f3] translate-y-[2px]";
  return (
    <button
      type={type}
      className={`min-h-11 rounded-pill px-4 py-2 text-sm font-medium transition ${variantClass} ${className}`.trim()}
      {...props}
    >
      {children}
    </button>
  );
}

export function UberLinkButton({
  to,
  children,
  className = "",
  variant = "primary",
}: {
  to: string;
  children: ReactNode;
  className?: string;
  variant?: ButtonVariant;
}) {
  const variantClass =
    variant === "primary"
      ? "bg-black text-white hover:bg-black/90"
      : variant === "secondary"
        ? "bg-white text-black hover:bg-[#e2e2e2]"
        : variant === "chip"
          ? "bg-[#efefef] text-black"
          : "bg-white text-black shadow-floating hover:bg-[#f3f3f3] translate-y-[2px]";
  return (
    <NavLink to={to} className={`inline-flex min-h-11 items-center justify-center rounded-pill px-4 py-2 text-sm font-medium transition ${variantClass} ${className}`.trim()}>
      {children}
    </NavLink>
  );
}

export function UberCard({ children, className = "", featured = false }: { children: ReactNode; className?: string; featured?: boolean }) {
  return (
    <section className={`${featured ? "rounded-featured" : "rounded-card"} bg-white p-6 shadow-card ${className}`.trim()}>
      {children}
    </section>
  );
}

export function UberSection({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`mx-auto w-full max-w-[1136px] px-4 md:px-6 ${className}`.trim()}>{children}</section>;
}

export function UberInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-card border border-black bg-white px-3 py-2 text-black placeholder:text-[#afafaf] ${props.className ?? ""}`.trim()}
    />
  );
}

export function UberPillNav({
  items,
  active,
  onSelect,
}: {
  items: { id: string; label: string }[];
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <nav className="no-scrollbar flex items-center gap-2 overflow-x-auto">
      {items.map((item) => (
        <UberButton key={item.id} variant="chip" className={active === item.id ? "bg-black text-white" : ""} onClick={() => onSelect(item.id)}>
          {item.label}
        </UberButton>
      ))}
    </nav>
  );
}
