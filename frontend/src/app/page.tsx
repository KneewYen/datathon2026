"use client";

import Link from "next/link";
import { useState } from "react";
import { INVESTMENT_QUESTION } from "@/lib/api";
import { PERSONAS, type PersonaId } from "@/lib/personas";


export default function Home() {
  const [personaId, setPersonaId] = useState<PersonaId>("amira");
  const persona = PERSONAS.find((item) => item.id === personaId)!;

  return (
    <main>

      <section className="hero" id="top">
        <div className="hero-copy">
          <span className="eyebrow">Cross-account investment intelligence</span>
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
          <p>{persona.goal}. The scenario remains fictional and does not use client data.</p>
        </aside>
      </section>

      <section className="workspace">
        <div className="workspace-kicker">
          <span>01</span>
          <p>Focused scenario</p>
          <b>TFSA + RRSP</b>
        </div>
        <div className="question-row">
          <h2>“{INVESTMENT_QUESTION}”</h2>
          <Link
            className="analyze-button"
            href={{ pathname: "/dashboard", query: { persona: personaId, run: "1" } }}
          >
            <span>Open analysis workspace</span>
            <b>↗</b>
          </Link>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 px-5 py-5">
          <p className="m-0 max-w-4xl text-sm leading-relaxed text-slate-600">
            The workspace reveals existing direct NVIDIA holdings, ETF look-through exposure,
            account-specific cash and risk effects, suitability conflicts, and every delegated
            agent and deterministic tool call used to reach the answer.
          </p>
        </div>
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
          The app workspace runs the S3-backed Lambda calculations, compares the fictional TFSA
          and RRSP, asks Bedrock for a grounded explanation, and renders the actual execution
          trace. No substitute cloud result is rendered on this landing page.
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
