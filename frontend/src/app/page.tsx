"use client";
import { useEffect, useRef, useState } from "react";
import { AccountsPanel } from "@/components/AccountsPanel";
import { Message, type ChatMessage } from "@/components/Message";
import { RiskSummary } from "@/components/RiskSummary";
import { api, type Account, type ChatResponse } from "@/lib/api";
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

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "assistant", data: WELCOME }]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selected, setSelected] = useState<Account | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.accounts().then(setAccounts).catch(() => {});
  }, []);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

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

  return (
    <div className="min-h-screen">
      <header className="border-b border-sky-100 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500 font-bold text-white">P</div>
            <div>
              <div className="font-semibold leading-tight">PortfolioGuard AI</div>
              <div className="text-xs text-slate-500">Team 62 · Datathon 2026</div>
            </div>
          </div>
          <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-100">
            Simulation
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-8 px-4 py-8">
        {/* Chat */}
        <section className="overflow-hidden rounded-3xl bg-white shadow-xl shadow-sky-100/60 ring-1 ring-sky-100">
          <div ref={scrollRef} className="h-[420px] space-y-4 overflow-y-auto bg-gradient-to-b from-sky-50/50 to-white p-5">
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
              <div className="flex items-center gap-2 pl-11 text-sm text-sky-600">
                <span className="h-2 w-2 animate-bounce rounded-full bg-sky-400" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-sky-400 [animation-delay:120ms]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-sky-400 [animation-delay:240ms]" />
              </div>
            )}
            {error && <div className="pl-11 text-sm text-red-600">{error}</div>}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex gap-2 border-t border-sky-100 p-3"
          >
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask me anything…"
              className="flex-1 rounded-full bg-sky-50/60 px-5 py-3 outline-none ring-1 ring-sky-100 transition placeholder:text-slate-400 focus:bg-white focus:ring-2 focus:ring-sky-400"
            />
            <button
              disabled={busy || !input.trim()}
              className="rounded-full bg-sky-500 px-6 py-3 font-medium text-white shadow-sm shadow-sky-200 transition hover:bg-sky-600 disabled:opacity-40"
            >
              Send
            </button>
          </form>
        </section>

        {/* Risk */}
        <RiskSummary accounts={accounts} />

        {/* Accounts */}
        <AccountsPanel
          accounts={accounts}
          selectedId={selected?.id ?? null}
          onSelect={selectAccount}
          onNew={() => send("I want to create a new account")}
        />

        <p className="pb-6 text-center text-xs text-slate-400">
          Simulation only · Fictional accounts · Not financial advice · No real trades
        </p>
      </main>
    </div>
  );
}
