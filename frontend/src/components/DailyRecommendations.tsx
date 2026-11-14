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
  return recs.slice(0, 4);
}

export function DailyRecommendations({
  accounts,
  onAsk,
}: {
  accounts: Account[];
  onAsk: (q: string) => void;
}) {
  const today = new Date().toLocaleDateString("en-CA", { weekday: "long", month: "short", day: "numeric" });
  return (
    <div className="rounded-3xl bg-white p-6 shadow-xl shadow-sky-100/60 ring-1 ring-sky-100">
      <div className="mb-4 flex items-baseline justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-sky-600">Daily recommendations</div>
          <div className="text-sm text-slate-500">{today}</div>
        </div>
        <span className="text-xs text-slate-400">Educational</span>
      </div>
      <ul className="space-y-2">
        {recommendations(accounts).map((r) => (
          <li key={r.title}>
            <button
              onClick={() => onAsk(r.ask)}
              className="group flex w-full items-start gap-3 rounded-2xl p-3 text-left transition hover:bg-sky-50"
            >
              <span className="mt-0.5 shrink-0 rounded-md bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-700">
                {r.tag}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold">{r.title}</span>
                <span className="block text-xs text-slate-500">{r.detail}</span>
              </span>
              <span className="self-center text-sky-400 transition group-hover:translate-x-0.5 group-hover:text-sky-600">→</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
