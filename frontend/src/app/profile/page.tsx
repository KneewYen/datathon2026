"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { RiskMeter } from "@/components/RiskMeter";
import { currentProfile } from "@/components/RiskSummary";
import { api, type Account } from "@/lib/api";
import { RISK_LEVEL, RISK_PROFILES } from "@/lib/profiles";

const PERSONA_INFO: Record<string, { age: number; goal: string; horizon: string; prefs: string[] }> = {
  Robert: { age: 59, goal: "Preserve capital, some growth", horizon: "3–5 yrs", prefs: ["Blue chips", "Stability", "No crypto"] },
  Mateo: { age: 41, goal: "Balanced growth", horizon: "8–12 yrs", prefs: ["ESG", "Balance", "No speculation"] },
  Amira: { age: 26, goal: "Long-term growth", horizon: "15+ yrs", prefs: ["AI / tech", "Crypto", "Diversified"] },
};

export default function ProfilePage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  useEffect(() => {
    api.accounts().then(setAccounts).catch(() => {});
  }, []);
  const profile = currentProfile(accounts);
  const info = profile ? PERSONA_INFO[profile.persona] : null;

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-8">
        <Link href="/" className="text-sm text-brand-600 hover:text-brand-700">← Back to dashboard</Link>

        <section className="flex items-center gap-5 rounded-3xl bg-white p-6 shadow-xl shadow-brand-100/60 ring-1 ring-brand-100">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-brand-100 text-3xl font-semibold text-brand-700">D</div>
          <div>
            <div className="text-xs uppercase tracking-wider text-brand-600">Profile</div>
            <h1 className="text-2xl font-semibold">Demo investor</h1>
            <p className="text-sm text-slate-500">{profile ? `Closest persona: ${profile.persona}` : "No persona matched yet"}</p>
          </div>
        </section>

        <section className="grid gap-4 sm:grid-cols-3">
          {[
            { k: "Risk type", v: profile?.label ?? "Not set" },
            { k: "Goal", v: info?.goal ?? "—" },
            { k: "Horizon", v: info?.horizon ?? "—" },
          ].map((x) => (
            <div key={x.k} className="rounded-2xl bg-white p-4 ring-1 ring-brand-100">
              <div className="text-xs text-slate-500">{x.k}</div>
              <div className="font-semibold">{x.v}</div>
            </div>
          ))}
        </section>

        {info && (
          <section className="rounded-3xl bg-white p-6 ring-1 ring-brand-100">
            <h2 className="mb-3 font-semibold">Preferences</h2>
            <div className="flex flex-wrap gap-2">
              {info.prefs.map((p) => (
                <span key={p} className="rounded-full bg-brand-50 px-3 py-1 text-sm text-brand-700 ring-1 ring-brand-100">{p}</span>
              ))}
            </div>
          </section>
        )}

        <section className="rounded-3xl bg-white p-6 ring-1 ring-brand-100">
          <h2 className="mb-3 font-semibold">Risk types</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            {RISK_PROFILES.map((r) => (
              <div key={r.id} className={`rounded-2xl p-4 ring-1 ${profile?.id === r.id ? "bg-brand-50 ring-2 ring-brand-500" : "ring-brand-100"}`}>
                <div className="font-semibold">{r.label}</div>
                <div className="mb-2 text-xs text-slate-500">Like {r.persona} · {r.horizon}</div>
                <RiskMeter level={r.level} />
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-3xl bg-white p-6 ring-1 ring-brand-100">
          <h2 className="mb-3 font-semibold">Accounts ({accounts.length})</h2>
          {accounts.length === 0 ? (
            <p className="text-sm text-slate-500">No accounts yet.</p>
          ) : (
            <ul className="divide-y divide-brand-50">
              {accounts.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-4 py-3">
                  <div>
                    <div className="font-medium">{a.name}</div>
                    <div className="text-xs text-slate-500">{a.horizon_agent} · {a.strategies.join(", ")}</div>
                  </div>
                  <div className="w-28">
                    <div className="mb-1 text-right text-xs text-brand-700">{a.risk_label}</div>
                    <RiskMeter level={RISK_LEVEL[a.risk] ?? 0} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <p className="text-center text-xs text-slate-400">Fictional profile · Simulation only · Not financial advice</p>
      </main>
    </div>
  );
}
