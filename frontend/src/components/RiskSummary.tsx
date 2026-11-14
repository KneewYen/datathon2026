import type { Account } from "@/lib/api";
import { RISK_LEVEL, RISK_PROFILES } from "@/lib/profiles";

export function currentProfile(accounts: Account[]) {
  if (!accounts.length) return null;
  const avg = Math.round(accounts.reduce((s, a) => s + (RISK_LEVEL[a.risk] ?? 0), 0) / accounts.length);
  return RISK_PROFILES.find((p) => p.level === avg) ?? null;
}

export function RiskSummary({ accounts }: { accounts: Account[] }) {
  const profile = currentProfile(accounts);
  const level = profile?.level ?? 0;
  const counts = RISK_PROFILES.map((p) => ({ ...p, n: accounts.filter((a) => a.risk === p.id).length }));

  return (
    <div className="flex h-full flex-col gap-6 rounded-3xl bg-gradient-to-br from-brand-500 to-brand-400 p-6 text-white shadow-xl shadow-brand-200">
      <div>
        <div className="text-xs uppercase tracking-wider text-brand-100">Your current risk type</div>
        <div className="mt-1 text-3xl font-semibold">{profile ? profile.label : "Not set yet"}</div>
        <div className="text-sm text-brand-100">
          {profile ? `${profile.horizon} focus` : "Open an account to set your risk"}
        </div>
      </div>

      <div>
        <div className="mb-1 flex justify-between text-xs text-brand-100">
          <span>Low</span>
          <span>High</span>
        </div>
        <div className="flex gap-1">
          {[1, 2, 3].map((i) => (
            <span key={i} className={`h-2.5 flex-1 rounded-full ${i <= level ? "bg-white" : "bg-white/30"}`} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-center">
        <div className="rounded-xl bg-white/15 p-2">
          <div className="text-xl font-semibold">{accounts.length}</div>
          <div className="text-xs text-brand-100">Accounts</div>
        </div>
        {counts.map((c) => (
          <div key={c.id} className="rounded-xl bg-white/15 p-2">
            <div className="text-xl font-semibold">{c.n}</div>
            <div className="text-xs text-brand-100">{c.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
