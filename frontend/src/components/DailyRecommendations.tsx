"use client";
import { useEffect, useState } from "react";
import type { Account } from "@/lib/api";

type Rec = { title: string; detail: string; ask: string; tag: string };

const BY_RISK: Record<string, Rec> = {
  conservative: {
    tag: "Bonds",
    title: "Check your bond exposure",
    detail: "Rate moves hit longer bonds harder. See what rates mean for your conservative account.",
    ask: "What do interest rates mean for me?",
  },
  balanced: {
    tag: "ESG",
    title: "Compare ESG vs. broad market",
    detail: "See how an ESG screen changes risk and return in your balanced account.",
    ask: "What is ESG investing?",
  },
  growth: {
    tag: "Crypto",
    title: "Keep crypto capped",
    detail: "Crypto has had drawdowns above 70%. Check it stays a small part of your growth account.",
    ask: "Should I hold crypto?",
  },
};

function recommendations(accounts: Account[]): Rec[] {
  const recs: Rec[] = [
    {
      tag: "Macro",
      title: "Today's recession signals",
      detail: "Yield curve and unemployment, from the latest data.",
      ask: "I'm worried about a recession",
    },
  ];
  if (!accounts.length) {
    recs.push(
      { tag: "Start", title: "Open your first account", detail: "Pick a horizon and a risk type.", ask: "I want to create a new account" },
      { tag: "Learn", title: "TFSA vs RRSP vs FHSA", detail: "Which account fits which goal.", ask: "TFSA vs RRSP vs FHSA?" }
    );
    return recs;
  }
  const risks = Array.from(new Set(accounts.map((a) => a.risk)));
  risks.forEach((r) => BY_RISK[r] && recs.push(BY_RISK[r]));
  if (risks.length === 1) {
    recs.push({
      tag: "Diversify",
      title: "All accounts share one risk type",
      detail: "Mixing horizons can spread your risk.",
      ask: "Why diversify?",
    });
  }
  return recs;
}

export function DailyRecommendations({
  accounts,
  onAsk,
}: {
  accounts: Account[];
  onAsk: (q: string) => void;
}) {
  // Format the date in the browser only, so server and client HTML match
  const [today, setToday] = useState("");
  useEffect(() => {
    setToday(new Date().toLocaleDateString("en-CA", { weekday: "long", month: "short", day: "numeric" }));
  }, []);
  return (
    <div className="flex h-full flex-col rounded-lg border border-slate-200 bg-white p-6">
      <h2 className="text-xl font-semibold">Daily recommendations</h2>
      <div className="h-5 text-xs text-slate-500">{today}</div>
      <ul className="mt-4 flex-1 overflow-y-auto border-t border-slate-200">
        {recommendations(accounts).map((r) => (
          <li key={r.title} className="border-b border-slate-200">
            <button onClick={() => onAsk(r.ask)} className="group w-full py-3 text-left">
              <span className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400">{r.tag}</span>
              <span className="block text-sm font-medium text-link group-hover:underline">{r.title}</span>
              <span className="block text-xs text-slate-500">{r.detail}</span>
            </button>
          </li>
        ))}
      </ul>
      <p className="pt-3 text-[11px] text-slate-400">Educational only. Not financial advice.</p>
    </div>
  );
}
