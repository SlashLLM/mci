import type { ReactNode } from "react";

export default function WorkerMobileShell({ children }: { children: ReactNode }) {
  return (
    <div className="w-full max-w-[430px] mx-auto min-h-[calc(100vh-5.5rem)] flex flex-col rounded-2xl border border-slate-800/80 bg-slate-900/40 shadow-[0_0_0_1px_rgba(15,23,42,0.8)] overflow-hidden">
      {children}
    </div>
  );
}
