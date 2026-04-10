import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api";

type NotificationRow = {
  id: number;
  title: string;
  body: string;
  read_at?: string | null;
  created_at?: string | null;
};

function fmtWhen(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export default function NotificationsPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<NotificationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    api<NotificationRow[]>("/notifications")
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 md:px-8">
      <h1 className="font-headline text-3xl md:text-4xl font-extrabold tracking-tight text-on-surface mb-2">
        {t("notifications_title")}
      </h1>
      <p className="text-sm text-on-surface-variant mb-8">{t("notifications_empty")}</p>
      {loading && <p className="text-sm text-on-surface-variant">{t("notifications_loading")}</p>}
      {err && <p className="text-sm text-error">{err}</p>}
      {!loading && !err && rows.length === 0 && <p className="text-sm text-on-surface-variant">{t("notifications_empty")}</p>}
      {!loading && !err && rows.length > 0 && (
        <ul className="space-y-3">
          {rows.map((n) => (
            <li key={n.id} className="rounded-2xl border border-outline-variant/15 bg-surface-container-lowest p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <p className="font-semibold text-on-surface">{n.title}</p>
                {!n.read_at && <span className="mt-1 h-2.5 w-2.5 rounded-full bg-error" />}
              </div>
              <p className="mt-1 text-sm text-on-surface-variant">{n.body}</p>
              {n.created_at ? (
                <p className="mt-2 text-[11px] uppercase tracking-wide text-on-surface-variant/80">{fmtWhen(n.created_at)}</p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

