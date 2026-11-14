import type { Account } from "@/lib/api";
import { RiskMeter } from "./RiskMeter";
import { RISK_LEVEL, RISK_PROFILES } from "@/lib/profiles";

export function currentProfile(accounts: Account[]) {
  if (!accounts.length) return null;
  const avg = Math.round(accounts.reduce((s, a) => s + (RISK_LEVEL[a.risk] ?? 0), 0) / accounts.length);
  return RISK_PROFILES.find((p) => p.level === avg) ?? null;
}

export function RiskSummary({ accounts }: { accounts: Account[] }) {
  const profile = currentProfile(accounts);
  const level = profile?.level ?? 0;
  const rows = [
    { k: "Accounts", v: accounts.length },
    ...RISK_PROFILES.map((p) => ({ k: p.label, v: accounts.filter((a) => a.risk === p.id).length })),
  ];

  return (
    <div className="flex-1 rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-500">My risk type</h2>
      <div className="mt-1 text-2xl font-semibold text-navy">{profile ? profile.label : "Not set yet"}</div>
      <div className="text-xs text-slate-500">
        {profile ? `${profile.horizon} focus` : "Open an account to set your risk"}
      </div>
      <div className="mt-4">
        <div className="mb-1 flex justify-between text-[11px] text-slate-500">
          <span>Low</span>
          <span>High</span>
        </div>
        <RiskMeter level={level} size="lg" />
      </div>
      <dl className="mt-5 divide-y divide-slate-200 border-y border-slate-200 text-sm">
        {rows.map((r) => (
          <div key={r.k} className="flex justify-between py-2">
            <dt className="text-slate-500">{r.k}</dt>
            <dd className="font-semibold">{r.v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
