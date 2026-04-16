import { useEffect, useState } from "react";
import { api } from "../../api";

type PersonaRole = "client" | "ta";

type AdminPersonaRow = {
  user_id: number;
  persona_id: number | null;
  role: string;
  display_name: string | null;
  email: string | null;
  phone: string | null;
  is_active: boolean;
  status: string;
  blacklist_reason?: string | null;
};

export function AdminPersonasPage({ role }: { role: PersonaRole }) {
  const [rows, setRows] = useState<AdminPersonaRow[]>([]);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "blacklisted">("all");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [blacklistTarget, setBlacklistTarget] = useState<AdminPersonaRow | null>(null);
  const [blacklistReason, setBlacklistReason] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function reload() {
    setErr(null);
    const params = new URLSearchParams({ include_inactive: "true" });
    const q = query.trim();
    if (q) params.set("q", q);
    const data = await api<AdminPersonaRow[]>(`/admin/personas/${role}?${params.toString()}`);
    setRows(data);
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);

  async function blacklist(userId: number, reason: string) {
    if (!reason.trim()) return;
    setBusyId(userId);
    setErr(null);
    try {
      await api(`/admin/personas/${userId}/blacklist`, { method: "POST", json: { reason: reason.trim() } });
      setBlacklistTarget(null);
      setBlacklistReason("");
      await reload();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusyId(null);
    }
  }

  async function unblacklist(userId: number) {
    setBusyId(userId);
    setErr(null);
    try {
      await api(`/admin/personas/${userId}/unblacklist`, { method: "POST" });
      await reload();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusyId(null);
    }
  }

  const title = role === "client" ? "Clients" : "TA";
  const filteredRows = rows.filter((row) => {
    if (statusFilter === "all") return true;
    return row.status === statusFilter;
  });

  return (
    <div className="space-y-5">
      {blacklistTarget && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4"
          role="presentation"
          onClick={() => {
            if (busyId !== blacklistTarget.user_id) {
              setBlacklistTarget(null);
              setBlacklistReason("");
            }
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="admin-blacklist-modal-title"
            className="bg-surface-container-lowest border border-outline-variant/25 rounded-2xl shadow-xl max-w-md w-full p-6 text-on-surface"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="admin-blacklist-modal-title" className="font-headline text-lg font-bold mb-2">
              Blacklist {blacklistTarget.display_name || blacklistTarget.email || `User #${blacklistTarget.user_id}`}
            </h2>
            <p className="text-sm text-on-surface-variant mb-4">
              Please provide a reason. This is required and will be saved in audit logs.
            </p>
            <label className="block text-xs font-medium text-on-surface-variant mb-1" htmlFor="blacklist-reason">
              Reason
            </label>
            <textarea
              id="blacklist-reason"
              className="min-h-28 w-full rounded-xl border border-outline-variant/30 bg-surface-container-low px-3 py-2 text-sm"
              value={blacklistReason}
              onChange={(e) => setBlacklistReason(e.target.value)}
              placeholder="Enter blacklist reason"
            />
            {!blacklistReason.trim() && <p className="mt-2 text-xs text-error">Reason is required.</p>}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="px-4 py-2 rounded-xl text-sm font-medium border border-outline-variant/30"
                disabled={busyId === blacklistTarget.user_id}
                onClick={() => {
                  setBlacklistTarget(null);
                  setBlacklistReason("");
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="px-4 py-2 rounded-xl text-sm font-semibold bg-error text-on-error disabled:opacity-50"
                disabled={busyId === blacklistTarget.user_id || !blacklistReason.trim()}
                onClick={() => void blacklist(blacklistTarget.user_id, blacklistReason)}
              >
                {busyId === blacklistTarget.user_id ? "Blacklisting..." : "Confirm Blacklist"}
              </button>
            </div>
          </div>
        </div>
      )}
      <div>
        <h1 className="font-headline text-3xl md:text-4xl font-extrabold text-on-surface tracking-tight mb-2">{title}</h1>
        <p className="text-on-surface-variant text-sm">Showing all personas by default, including blacklisted accounts.</p>
      </div>
      {err && <p className="text-sm text-error">{err}</p>}
      <div className="flex flex-wrap gap-2">
        <input
          className="rounded-xl border border-outline-variant/30 bg-surface-container-low px-3 py-2 text-sm"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Search ${title}`}
        />
        <select
          className="rounded-xl border border-outline-variant/30 bg-surface-container-low px-3 py-2 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as "all" | "active" | "blacklisted")}
          aria-label={`${title} status filter`}
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="blacklisted">Blacklisted</option>
        </select>
        <button
          type="button"
          className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary"
          onClick={() => void reload()}
        >
          Filter
        </button>
      </div>
      <div className="overflow-x-auto rounded-xl border border-outline-variant/20">
        <table className="w-full min-w-[760px] text-left text-sm text-on-surface">
          <thead className="bg-surface-container-low text-xs uppercase text-on-surface-variant">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Phone</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Reason</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => (
              <tr key={row.user_id} className="border-t border-outline-variant/10">
                <td className="px-3 py-2 font-medium">{row.display_name || "—"}</td>
                <td className="px-3 py-2">{row.email || "—"}</td>
                <td className="px-3 py-2">{row.phone || "—"}</td>
                <td className="px-3 py-2">{row.status}</td>
                <td className="px-3 py-2 text-on-surface-variant">{row.status === "blacklisted" ? row.blacklist_reason || "—" : "—"}</td>
                <td className="px-3 py-2 text-right">
                  {row.status !== "blacklisted" ? (
                    <button
                      type="button"
                      className="text-sm font-semibold text-error hover:underline disabled:opacity-50"
                      disabled={busyId === row.user_id}
                      onClick={() => {
                        setBlacklistTarget(row);
                        setBlacklistReason("");
                      }}
                    >
                      {busyId === row.user_id ? "Blacklisting..." : "Blacklist"}
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="text-sm font-semibold text-primary hover:underline disabled:opacity-50"
                      disabled={busyId === row.user_id}
                      onClick={() => void unblacklist(row.user_id)}
                    >
                      {busyId === row.user_id ? "Updating..." : "Unblacklist"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
