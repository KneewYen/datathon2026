import type { Account } from "@/lib/api";

const RISK_STYLE: Record<string, string> = {
  conservative: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300",
  balanced: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  growth: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300",
};

export function AccountsPanel({ accounts, onNew }: { accounts: Account[]; onNew: () => void }) {
  return (
    <aside className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">My accounts</h2>
        <button onClick={onNew} className="text-sm underline">+ New</button>
      </div>
      {accounts.length === 0 && (
        <p className="text-sm text-neutral-500">No accounts yet. Ask the assistant to create one.</p>
      )}
      <ul className="space-y-2">
        {accounts.map((a) => (
          <li key={a.id} className="rounded-lg border border-neutral-200 p-3 dark:border-neutral-800">
            <div className="flex items-center justify-between">
              <span className="font-medium">{a.name}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs ${RISK_STYLE[a.risk] ?? ""}`}>{a.risk_label}</span>
            </div>
            <div className="mt-1 text-xs text-neutral-500">
              {a.horizon_agent} · like {a.persona}
            </div>
            <div className="mt-1 text-xs text-neutral-500">{a.strategies.join(" · ")}</div>
          </li>
        ))}
      </ul>
    </aside>
  );
}
