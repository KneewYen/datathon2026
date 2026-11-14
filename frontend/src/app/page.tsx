"use client";

import Link from "next/link";
import { useState } from "react";
import { AllocationComparison } from "@/components/AllocationComparison";
import { PERSONAS, allocationLabel, formatCad, proposedAllocations, type PersonaId } from "@/lib/personas";




export default function Home() {
  const [personaId, setPersonaId] = useState<PersonaId>("amira");
  const persona = PERSONAS.find((item) => item.id === personaId)!;

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
          <div className="persona-holdings">
            <div><strong>{formatCad(persona.startingBalance)}</strong><span>starting balance</span></div>
            <div><strong>{allocationLabel(persona.allocations)}</strong><span>starting allocation</span></div>
          </div>
          <p>{persona.goal}. The scenario remains fictional and does not use client data.</p>
        </aside>
      </section>

      <section className="workspace">
        <div className="workspace-kicker">
          <span>01</span>
          <p>Focused scenario</p>
          <b>TFSA</b>
        </div>
        <div className="question-row">
          <h2>“{persona.scenario.question}”</h2>
          <Link
            className="analyze-button"
            href={{ pathname: "/dashboard", query: { persona: personaId, run: "1" } }}
          >
            <span>Analyze with live AWS</span>
            <b>↗</b>
          </Link>
        </div>
        <AllocationComparison
          current={persona.allocations}
          proposed={proposedAllocations(persona)}
        />
        <div className="method-strip">
          <span><b>S3</b> Versioned market data</span>
          <span><b>λ</b> Deterministic calculations</span>
          <span><b>BR</b> Grounded Bedrock explanation</span>
          <span><b>✓</b> Governance checks</span>
        </div>
      </section>

      <section className="preflight">
        <div><span>02</span><h2>Continue in the demo workspace</h2></div>
        <p>
          The app workspace runs the approved S3-backed Lambda calculation, asks Bedrock for a
          grounded explanation, and shows the observable agent trace. No substitute live result
          is rendered on this landing page.
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
