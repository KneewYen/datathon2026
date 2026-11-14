import type { Account } from "@/lib/api";
import { RISK_LEVEL } from "@/lib/profiles";
import { RiskMeter } from "./RiskMeter";

const HORIZON: Record<string, string> = { short: "3–5 yrs", mid: "8–12 yrs", long: "15+ yrs" };

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
    <section className="space-y-5 rounded-3xl bg-white p-5 shadow-xl shadow-sky-100/60 ring-1 ring-sky-100 sm:p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">My accounts</h2>
          <p className="text-xs text-slate-500">Click an account to ask about it</p>
        </div>
        <button
          onClick={onNew}
          aria-label="Create account"
          title="Create account"
          className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-500 text-2xl leading-none text-white shadow-md shadow-sky-200 transition hover:scale-105 hover:bg-sky-600"
        >
          +
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
        {accounts.map((a) => {
          const active = a.id === selectedId;
          return (
            <button
              key={a.id}
              onClick={() => onSelect(a)}
              className={`group rounded-2xl bg-sky-50/40 p-5 text-left ring-1 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-sky-100 ${
                active ? "ring-2 ring-sky-500 shadow-lg shadow-sky-100" : "ring-sky-100"
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs font-medium uppercase tracking-wider text-sky-600">{a.type}</div>
                  <div className="mt-0.5 text-lg font-semibold">{a.name}</div>
                </div>
                <span className="rounded-full bg-sky-50 px-2.5 py-0.5 text-xs font-medium text-sky-700">
                  {a.risk_label}
                </span>
              </div>
              <div className="mt-4">
                <RiskMeter level={RISK_LEVEL[a.risk] ?? 0} />
              </div>
              <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
                <span>{a.horizon_agent}</span>
                <span>{HORIZON[a.horizon]}</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {a.strategies.map((s) => (
                  <span key={s} className="rounded-md bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
                    {s}
                  </span>
                ))}
              </div>
            </button>
          );
        })}

        <button
          onClick={onNew}
          className="flex min-h-[180px] flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-sky-200 text-sky-600 transition hover:border-sky-400 hover:bg-sky-50"
        >
          <span className="text-3xl leading-none">+</span>
          <span className="text-sm font-medium">Open an account</span>
        </button>
      </div>
    </section>
  );
}
