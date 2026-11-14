"use client";
import { useEffect, useRef, useState } from "react";
import { AccountsPanel } from "@/components/AccountsPanel";
import { Message, type ChatMessage } from "@/components/Message";
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
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.accounts().then(setAccounts).catch(() => {});
  }, []);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

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
    if (!text.trim() || busy) return;
    setInput("");
    run(() => api.chat(text.trim()), text.trim());
  };

  return (
    <main className="mx-auto grid min-h-screen max-w-6xl gap-6 px-4 py-6 md:grid-cols-[260px_1fr]">
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-bold">PortfolioGuard AI</h1>
          <p className="text-xs text-neutral-500">Team 62 · Datathon 2026</p>
        </div>
        <AccountsPanel accounts={accounts} onNew={() => send("I want to create a new account")} />
      </div>

      <section className="flex min-h-[70vh] flex-col rounded-2xl border border-neutral-200 dark:border-neutral-800">
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
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
          {busy && <div className="text-sm text-neutral-500">Thinking…</div>}
          {error && <div className="text-sm text-red-600">{error}</div>}
          <div ref={endRef} />
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2 border-t border-neutral-200 p-3 dark:border-neutral-800"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask me anything…"
            className="flex-1 rounded-lg border border-neutral-200 bg-transparent px-3 py-2 dark:border-neutral-800"
          />
          <button disabled={busy || !input.trim()} className="rounded-lg bg-neutral-900 px-4 py-2 text-white disabled:opacity-40 dark:bg-white dark:text-neutral-900">
            Send
          </button>
        </form>
        <p className="px-3 pb-3 text-xs text-neutral-500">Simulation only. Fictional accounts. Not financial advice. No real trades.</p>
      </section>
    </main>
  );
}
