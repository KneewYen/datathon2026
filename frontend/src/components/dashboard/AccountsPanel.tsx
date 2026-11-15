import type { Account } from "@/lib/api";
import { RISK_LEVEL } from "@/lib/profiles";
import { RiskMeter } from "./RiskMeter";

const HORIZON: Record<string, string> = { short: "3–5 yrs", mid: "8–12 yrs", long: "15+ yrs" };

function Flag() {
  return (
    <svg viewBox="0 0 16 16" className="h-4 w-4 shrink-0 text-brand-500" fill="currentColor" aria-hidden>
      <path d="M2 1h1.5v14H2zM4 2h9l-2 3.2L13 8.5H4z" />
    </svg>
  );
}

export function AccountsPanel({
  accounts,
  selectedId,
  onSelect,
  onNew,
}: {
  accounts: Account[];
  selectedId: string | null;
  onSelect: (a: Account) => void;
  onNew: () => void;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 sm:p-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold">My accounts</h2>
          <p className="text-xs text-slate-500">Click an account to ask about it</p>
        </div>
        <button
          onClick={onNew}
          aria-label="Create account"
          title="Create account"
          className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-500 text-2xl leading-none text-white transition hover:bg-brand-600"
        >
          +
        </button>
      </div>

      <h3 className="mt-5 border-b border-slate-200 pb-2 text-sm font-semibold">My simulated accounts</h3>
      {accounts.length === 0 && <p className="py-4 text-sm text-slate-500">No accounts yet. Use + to open one.</p>}
      <ul>
        {accounts.map((a) => (
          <li key={a.id} className="border-b border-slate-200">
            <button
              onClick={() => onSelect(a)}
              className={`flex w-full items-center gap-3 px-2 py-4 text-left transition hover:bg-slate-50 ${
                a.id === selectedId ? "bg-slate-50 shadow-[inset_3px_0_0_#e41c23]" : ""
              }`}
            >
              <Flag />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{a.name}</span>
                <span className="block truncate text-xs text-slate-500">
                  {a.horizon_profile} · {HORIZON[a.horizon]} · {a.strategies.join(", ")}
                </span>
              </span>
              <span className="w-28 shrink-0">
                <span className="mb-1 block text-right text-sm font-semibold">{a.risk_label}</span>
                <RiskMeter level={RISK_LEVEL[a.risk] ?? 0} />
              </span>
            </button>
          </li>
        ))}
      </ul>
      <button onClick={onNew} className="mt-3 text-sm font-medium text-link hover:underline">
        + Open an account
      </button>
      <p className="mt-3 text-[11px] text-slate-400">
        Fictional accounts are stored in memory for this demo session only.
      </p>
    </section>
  );
}
