"use client";
import { use, useEffect, useRef, useState } from "react";
import { AccountsPanel } from "@/components/dashboard/AccountsPanel";
import { Message, type ChatMessage } from "@/components/dashboard/Message";
import { RiskSummary } from "@/components/dashboard/RiskSummary";
import { Header } from "@/components/dashboard/Header";
import { PillButton } from "@/components/dashboard/PillButton";
import { DailyRecommendations } from "@/components/dashboard/DailyRecommendations";
import { LiveAnalysisPanel } from "@/components/dashboard/LiveAnalysisPanel";
import { InvestmentIntelligencePanel } from "@/components/dashboard/InvestmentIntelligencePanel";
import {
  api,
  runAnalysis,
  type Account,
  type AnalysisResponse,
  type ApiMeta,
  type ChatResponse,
} from "@/lib/api";
import { type PersonaId } from "@/lib/personas";
import { FAQ } from "@/lib/profiles";

const WELCOME: ChatResponse = {
  answer: "Ask me anything.",
  trace: [],
  metrics: {},
  sources: [],
  warnings: [],
  proposal: null,
  suggestions: FAQ,
};

type SearchParams = Promise<{ persona?: string | string[]; run?: string | string[] }>;

function first(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function personaFrom(value: string | undefined): PersonaId {
  return value === "mateo" || value === "robert" ? value : "amira";
}

export default function DashboardPage({ searchParams }: { searchParams: SearchParams }) {
  const query = use(searchParams);
  const initialPersona = personaFrom(first(query.persona));
  const autoRun = first(query.run) === "1";
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "assistant", data: WELCOME }]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selected, setSelected] = useState<Account | null>(null);
  const [personaId, setPersonaId] = useState<PersonaId>(initialPersona);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [meta, setMeta] = useState<ApiMeta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.accounts().then(setAccounts).catch((reason) => {
      setError(reason instanceof Error ? reason.message : "Could not load accounts");
    });
    api.meta().then(setMeta).catch((reason) => {
      setMetaError(reason instanceof Error ? reason.message : "Could not reach the API");
    });
  }, []);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  const executeAnalysis = async (requestedPersona: PersonaId) => {
    setAnalysisBusy(true);
    setAnalysisError(null);
    try {
      setAnalysis(await runAnalysis(requestedPersona));
    } catch (reason) {
      setAnalysis(null);
      setAnalysisError(reason instanceof Error ? reason.message : "Live AWS analysis failed");
    } finally {
      setAnalysisBusy(false);
    }
  };

  async function run(fn: () => Promise<ChatResponse>, userText?: string, resolveId?: string) {
    setBusy(true);
    setError(null);
    setMessages((m) => {
      let next = m;
      if (resolveId) {
        next = next.map((x) =>
          x.role === "assistant" && x.data.proposal?.id === resolveId ? { ...x, resolved: true } : x
        );
      }
      return userText ? [...next, { role: "user", text: userText }] : next;
    });
    try {
      const data = await fn();
      setMessages((m) => [...m, { role: "assistant", data }]);
      setAccounts(await api.accounts());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  const send = (text: string) => {
    const t = text.trim();
    if (!t || busy) return;
    setInput("");
    run(() => api.chat(t), t);
  };

  const selectAccount = (a: Account) => {
    setSelected(a);
    setInput(`How risky is my ${a.name}?`);
    inputRef.current?.focus();
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const changePersona = (next: PersonaId) => {
    setPersonaId(next);
    setAnalysis(null);
    setAnalysisError(null);
  };

  return (
    <div className="min-h-screen">
      <Header />

      <main className="mx-auto grid max-w-[1760px] gap-6 px-4 py-8 lg:grid-cols-[230px_minmax(0,1fr)_250px]">
        {/* Left: current risk type, top to bottom */}
        <aside className="flex flex-col gap-4 lg:sticky lg:top-[73px] lg:h-[calc(100vh-73px-4rem)]">
          <div className="space-y-3">
            <PillButton icon="+" onClick={() => send("I want to create a new account")}>Open an account</PillButton>
            <PillButton icon="?" onClick={() => inputRef.current?.focus()}>Ask a question</PillButton>
          </div>
          <RiskSummary accounts={accounts} />
        </aside>

        {/* Middle: chat + accounts */}
        <div className="min-w-0 space-y-6">
        <InvestmentIntelligencePanel autoRun={autoRun} />

        <details className="overflow-hidden rounded-lg bg-white ring-1 ring-slate-200">
          <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-navy">
            Earlier strategy-shift scenario
          </summary>
          <div className="border-t border-slate-200">
            <LiveAnalysisPanel
              personaId={personaId}
              onPersonaChange={changePersona}
              result={analysis}
              busy={analysisBusy}
              error={analysisError}
              meta={meta}
              metaError={metaError}
              onRun={() => void executeAnalysis(personaId)}
            />
          </div>
        </details>

        {/* Chat */}
        <section className="overflow-hidden rounded-lg bg-white ring-1 ring-slate-200">
          <div ref={scrollRef} className="h-[420px] space-y-4 overflow-y-auto bg-white p-5">
            {messages.map((m, i) => (
              <Message
                key={i}
                msg={m}
                busy={busy}
                onSuggestion={send}
                onApprove={(id, risk) => run(() => api.approve(id, risk), "Approve", id)}
                onReject={(id) => run(() => api.reject(id), "Decline", id)}
              />
            ))}
            {busy && (
              <div className="flex items-center gap-2 pl-11 text-sm text-brand-600">
                <span className="h-2 w-2 animate-bounce rounded-full bg-brand-400" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-brand-400 [animation-delay:120ms]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-brand-400 [animation-delay:240ms]" />
              </div>
            )}
            {error && <div className="pl-11 text-sm text-red-600">{error}</div>}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex gap-2 border-t border-slate-200 p-3"
          >
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask me anything…"
              className="flex-1 rounded-full bg-white px-5 py-3 outline-none ring-1 ring-slate-300 transition placeholder:text-slate-400 focus:ring-2 focus:ring-navy"
            />
            <button
              disabled={busy || !input.trim()}
              className="rounded-full bg-brand-500 px-6 py-3 font-medium text-white shadow-sm shadow-brand-200 transition hover:bg-brand-600 disabled:opacity-40"
            >
              Send
            </button>
          </form>
        </section>


        {/* Accounts */}
        <AccountsPanel
          accounts={accounts}
          selectedId={selected?.id ?? null}
          onSelect={selectAccount}
          onNew={() => send("I want to create a new account")}
        />

        </div>

        {/* Right: daily recommendations, top to bottom */}
        <aside className="lg:sticky lg:top-[73px] lg:h-[calc(100vh-73px-4rem)]">
          <DailyRecommendations
            accounts={accounts}
            onAsk={(q) => {
              window.scrollTo({ top: 0, behavior: "smooth" });
              send(q);
            }}
          />
        </aside>

        <p className="pb-6 text-center text-xs text-slate-400 lg:col-span-3">
          Simulation only · Fictional accounts · Not financial advice · No real trades
        </p>
      </main>
    </div>
  );
}
