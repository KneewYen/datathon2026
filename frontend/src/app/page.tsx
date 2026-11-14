"use client";
import { useState } from "react";
import { Stepper } from "@/components/Stepper";
import { PersonaPicker } from "@/components/PersonaPicker";
import { AskPanel } from "@/components/AskPanel";
import { ResultView } from "@/components/ResultView";
import { sendChat, type ChatResponse } from "@/lib/api";
import type { Persona } from "@/lib/personas";

export default function Home() {
  const [persona, setPersona] = useState<Persona | null>(null);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const step = !persona ? 0 : !result ? 1 : 2;

  async function ask(q: string) {
    if (!persona) return;
    setLoading(true);
    setError(null);
    setQuestion(q);
    try {
      setResult(await sendChat(persona.id, q));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl space-y-8 px-4 py-10">
      <header className="space-y-4">
        <h1 className="text-2xl font-bold">PortfolioGuard AI</h1>
        <Stepper current={step} />
      </header>

      {step === 0 && <PersonaPicker onPick={setPersona} />}

      {step === 1 && persona && (
        <AskPanel persona={persona} loading={loading} onAsk={ask} onBack={() => setPersona(null)} />
      )}

      {step === 2 && result && (
        <ResultView question={question} result={result} onNew={() => setResult(null)} />
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <footer className="border-t border-neutral-200 pt-4 text-xs text-neutral-500 dark:border-neutral-800">
        Simulation only. Fictional personas. Not financial advice. No real trades.
      </footer>
    </main>
  );
}
