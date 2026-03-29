import { useTranslation } from "react-i18next";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { clearSession, getRole, getToken } from "./api";
import LoginPage from "./pages/LoginPage";
import WorkerApp from "./pages/worker/WorkerApp";
import WorkerSignupPage from "./pages/worker/WorkerSignupPage";
import WorkerWelcomePage from "./pages/worker/WorkerWelcomePage";
import { JobOrderDetailView } from "./components/jobOrder/JobOrderDetailView";
import {
  ClientLayout,
  ClientJobsList,
  ClientNewJob,
  ClientTimesheetsPage,
  ClientLivePage,
} from "./pages/client/ClientApp";
import {
  TaLayout,
  TaJobsList,
  TaNewJobPage,
  TaAnalyticsPage,
  TaExportsPage,
  TaTimesheetsPage,
  TaPayrollPage,
} from "./pages/ta/TaApp";

function GuardWorker({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  if (getRole() !== "worker") return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function GuardTa({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  const r = getRole();
  if (r !== "ta" && r !== "admin") return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function GuardClient({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  if (getRole() !== "client") return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function HomeRedirect() {
  const t = getToken();
  const r = getRole();
  if (!t) return <Navigate to="/login" replace />;
  if (r === "worker") return <Navigate to="/worker" replace />;
  if (r === "client") return <Navigate to="/client" replace />;
  return <Navigate to="/ta" replace />;
}

function useWorkerPortalFullBleed(): boolean {
  const { pathname } = useLocation();
  if (pathname.startsWith("/worker/welcome") || pathname.startsWith("/worker/signup")) return false;
  return pathname === "/worker" || pathname.startsWith("/worker/");
}

function useClientPortalFullBleed(): boolean {
  const { pathname } = useLocation();
  return pathname === "/client" || pathname.startsWith("/client/");
}

export default function App() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const workerPortal = useWorkerPortalFullBleed();
  const clientPortal = useClientPortalFullBleed();

  const routes = (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/worker/welcome" element={<WorkerWelcomePage />} />
      <Route path="/worker/signup" element={<WorkerSignupPage />} />
      <Route
        path="/worker/*"
        element={
          <GuardWorker>
            <WorkerApp />
          </GuardWorker>
        }
      />
      <Route
        path="/ta"
        element={
          <GuardTa>
            <TaLayout />
          </GuardTa>
        }
      >
        <Route index element={<TaJobsList />} />
        <Route path="new" element={<TaNewJobPage />} />
        <Route path="analytics" element={<TaAnalyticsPage />} />
        <Route path="exports" element={<TaExportsPage />} />
        <Route path="timesheets" element={<TaTimesheetsPage />} />
        <Route path="payroll" element={<TaPayrollPage />} />
        <Route path=":jobId" element={<JobOrderDetailView variant="ta" basePath="/ta" />} />
      </Route>
      <Route
        path="/client"
        element={
          <GuardClient>
            <ClientLayout />
          </GuardClient>
        }
      >
        <Route index element={<ClientJobsList />} />
        <Route path="new" element={<ClientNewJob />} />
        <Route path="timesheets" element={<ClientTimesheetsPage />} />
        <Route path="live" element={<ClientLivePage />} />
        <Route path=":jobId" element={<JobOrderDetailView variant="client" basePath="/client" />} />
      </Route>
      <Route path="/" element={<HomeRedirect />} />
    </Routes>
  );

  if (workerPortal || clientPortal) {
    return routes;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/90 px-4 py-3 backdrop-blur">
        <button
          type="button"
          className="text-left font-semibold text-sky-400"
          onClick={() => navigate(getToken() ? "/" : "/login")}
        >
          {t("app_title")}
        </button>
        <div className="flex items-center gap-2">
          <label className="sr-only text-xs text-slate-400">{t("language")}</label>
          <select
            className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
            value={i18n.language.startsWith("zh") ? "zh" : "en"}
            onChange={(e) => {
              const lng = e.target.value;
              i18n.changeLanguage(lng);
              localStorage.setItem("locale", lng);
            }}
          >
            <option value="en">English</option>
            <option value="zh">简体中文</option>
          </select>
          {getToken() && (
            <button
              type="button"
              className="text-xs text-slate-400 underline"
              onClick={() => {
                clearSession();
                navigate("/login");
              }}
            >
              Log out
            </button>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{routes}</main>
    </div>
  );
}
