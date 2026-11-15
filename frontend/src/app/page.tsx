"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AllocationComparison, applyShift } from "@/components/AllocationComparison";
import { api, type ApiMeta } from "@/lib/api";
import { PERSONAS, type PersonaId } from "@/lib/personas";


export default function Home() {
  const [personaId, setPersonaId] = useState<PersonaId>("amira");
  const [meta, setMeta] = useState<ApiMeta | null>(null);
  const persona = PERSONAS.find((item) => item.id === personaId)!;
  const scenario = meta?.scenarios?.[personaId];

  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
  }, []);

  return (
    <main>

      <section className="hero" id="top">
        <div className="hero-copy">
          <span className="eyebrow">Fictional portfolio decision support</span>
          <h1>See the trade-off<br />before the allocation changes.</h1>
          <p>
            PortfolioGuard coordinates account and strategy agents, calculates every metric
            in AWS, and shows the evidence behind the answer.
          </p>
        </div>
        <aside className="persona-panel">
          <span className="panel-label">Investor context</span>
          <div className="persona-tabs" role="tablist" aria-label="Fictional investor persona">
            {PERSONAS.map((item) => (
              <button
                key={item.id}
                className={item.id === personaId ? "active" : ""}
                onClick={() => setPersonaId(item.id)}
                role="tab"
                aria-selected={item.id === personaId}
              >
                {item.name}
              </button>
            ))}
          </div>
          <div className="persona-summary">
            <div><strong>{persona.age}</strong><span>age</span></div>
            <div><strong>{persona.horizon}</strong><span>horizon</span></div>
            <div><strong>{persona.risk}</strong><span>risk profile</span></div>
          </div>
          <p>
            {persona.goal}. What this persona tests: {persona.tests.toLowerCase()}. The scenario remains fictional
            and does not use client data.
          </p>
        </aside>
      </section>

      <section className="workspace">
        <div className="workspace-kicker">
          <span>01</span>
          <p>Focused scenario</p>
          <b>{scenario?.account_type ?? "…"}</b>
        </div>
        <div className="question-row">
          <h2>“{scenario?.question ?? "Start the API to load this persona's scenario."}”</h2>
          <Link
            className="analyze-button"
            href={{ pathname: "/dashboard", query: { persona: personaId, run: "1" } }}
          >
            <span>Analyze with live AWS</span>
            <b>↗</b>
          </Link>
        </div>
        {scenario && (
          <AllocationComparison
            current={scenario.strategy_allocations}
            proposed={applyShift(scenario.strategy_allocations, scenario.shift)}
            shiftAmount={scenario.shift.amount}
            accountType={scenario.account_type}
          />
        )}
        <div className="method-strip">
          <span><b>S3</b> Versioned market data</span>
          <span><b>λ</b> Calculations + 2022 stress replay</span>
          <span><b>BR</b> Bedrock prose, numbers inserted by code</span>
          <span><b>✓</b> Persona risk budget pushes back</span>
        </div>
      </section>

      <section className="preflight">
        <div><span>02</span><h2>Continue in the demo workspace</h2></div>
        <p>
          The workspace runs the S3-backed Lambda calculation, replays 2022, applies each persona&apos;s
          risk budget, and lets you challenge a specific request such as &ldquo;Put 25% of my RRSP in
          NVDA&rdquo;. The advisor will not simply agree: it shows what fits instead. No substitute live
          result is rendered on this landing page.
        </p>
      </section>

      <footer>
        <div className="brand"><span>PG</span><div>PortfolioGuard <b>AI</b></div></div>
        <p>Simulation only · Fictional portfolios · Not financial advice · No real trades</p>
        <small>AlphaForge AI Datathon 2026 · Team 62</small>
      </footer>
    </main>
  );
}
