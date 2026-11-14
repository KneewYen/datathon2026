import type { Account } from "@/lib/api";
import { RISK_LEVEL, RISK_PROFILES } from "@/lib/profiles";

export function RiskSummary({ accounts }: { accounts: Account[] }) {
  const avg = accounts.length
    ? Math.round(accounts.reduce((s, a) => s + (RISK_LEVEL[a.risk] ?? 0), 0) / accounts.length)
    : 0;
  const profile = RISK_PROFILES.find((p) => p.level === avg);

  return (
    <div className="flex flex-col gap-4 rounded-2xl bg-gradient-to-br from-sky-500 to-sky-400 p-5 text-white shadow-lg shadow-sky-200 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div className="text-xs uppercase tracking-wider text-sky-100">Your current risk type</div>
        <div className="mt-1 text-2xl font-semibold">{profile ? profile.label : "Not set yet"}</div>
        <div className="text-sm text-sky-100">
          {profile ? `Similar to ${profile.persona} · ${profile.horizon}` : "Open an account to set your risk"}
        </div>
      </div>
      <div className="flex gap-6 text-sm">
        <div>
          <div className="text-2xl font-semibold">{accounts.length}</div>
          <div className="text-sky-100">Accounts</div>
        </div>
        <div className="w-40 self-center">
          <div className="mb-1 flex justify-between text-xs text-sky-100">
            <span>Low</span>
            <span>High</span>
          </div>
          <div className="flex gap-1">
            {[1, 2, 3].map((i) => (
              <span key={i} className={`h-2.5 flex-1 rounded-full ${i <= avg ? "bg-white" : "bg-white/30"}`} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
