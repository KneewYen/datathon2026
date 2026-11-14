"use client";
import { useState } from "react";
import type { Persona } from "@/lib/personas";

export function AskPanel({
  persona,
  loading,
  onAsk,
  onBack,
}: {
  persona: Persona;
  loading: boolean;
  onAsk: (q: string) => void;
  onBack: () => void;
}) {
  const [q, setQ] = useState("");
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm">
        <span>
          Investor: <b>{persona.name}</b> · {persona.horizonAgent} ({persona.strategies.join(", ")})
        </span>
        <button onClick={onBack} className="text-neutral-500 underline">Change</button>
      </div>
      <div className="flex flex-wrap gap-2">
        {persona.prompts.map((p) => (
          <button
            key={p}
            onClick={() => setQ(p)}
            className="rounded-full border border-neutral-200 px-3 py-1 text-sm dark:border-neutral-800"
          >
            {p}
          </button>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) onAsk(q.trim());
        }}
        className="flex gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={`Ask about ${persona.name}'s portfolio…`}
          className="flex-1 rounded-lg border border-neutral-200 bg-transparent px-3 py-2 dark:border-neutral-800"
        />
        <button
          disabled={loading || !q.trim()}
          className="rounded-lg bg-neutral-900 px-4 py-2 text-white disabled:opacity-40 dark:bg-white dark:text-neutral-900"
        >
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </form>
    </div>
  );
}
