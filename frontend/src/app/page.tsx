"use client";

import { useState } from "react";
import { AllocationComparison } from "@/components/AllocationComparison";
import { MetricCards } from "@/components/MetricCards";
import { PerformanceChart } from "@/components/PerformanceChart";
import { TraceTimeline } from "@/components/TraceTimeline";
import { DEMO_QUESTION, runAnalysis, type AnalysisResponse } from "@/lib/api";
import { PERSONAS, type PersonaId } from "@/lib/personas";


const CURRENT = { growth: 0.6, dividend: 0.2, momentum: 0.1, preservation: 0.1 };
const PROPOSED = { growth: 0.4, dividend: 0.4, momentum: 0.1, preservation: 0.1 };


export default function Home() {
  const [personaId, setPersonaId] = useState<PersonaId>("amira");
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const persona = PERSONAS.find((item) => item.id === personaId)!;

  async function analyze() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await runAnalysis(personaId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Live analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <nav className="topbar">
        <a className="brand" href="#top" aria-label="PortfolioGuard AI home">
          <span>PG</span>
          <div>PortfolioGuard <b>AI</b></div>
        </a>
        <div className="top-status"><i /> AWS-backed evidence engine</div>
        <a className="nav-link" href="#method">Methodology</a>
      </nav>

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
                onClick={() => { setPersonaId(item.id); setResult(null); setError(null); }}
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
          <b>TFSA</b>
        </div>
        <div className="question-row">
          <h2>“{DEMO_QUESTION}”</h2>
          <button className="analyze-button" onClick={analyze} disabled={loading}>
            <span>{loading ? "Running AWS analysis" : "Analyze with live AWS"}</span>
            <b>{loading ? "···" : "↗"}</b>
          </button>
        </div>
        <AllocationComparison
          current={result?.current_allocations ?? CURRENT}
          proposed={result?.proposed_allocations ?? PROPOSED}
        />
        <div className="method-strip">
          <span><b>S3</b> Versioned market data</span>
          <span><b>λ</b> Deterministic calculations</span>
          <span><b>BR</b> Grounded Bedrock explanation</span>
          <span><b>✓</b> Governance checks</span>
        </div>
      </section>

      {error && (
        <section className="error-banner" role="alert">
          <div><span>Connection required</span><strong>{error}</strong></div>
          <p>No substitute result is shown. Configure the approved Lambda and Bedrock services, then retry.</p>
        </section>
      )}

      {result ? (
        <section className="results" aria-live="polite">
          <div className={`conclusion ${result.conclusion}`}>
            <span className="eyebrow">Evidence-backed answer</span>
            <div>
              <h2>{result.conclusion === "risk_reduced" ? "Measured risk decreased." : "The evidence is mixed."}</h2>
              <p>{result.answer}</p>
            </div>
            <small>Bedrock model<br /><b>{result.model_id}</b></small>
          </div>

          <section className="result-section">
            <header className="section-heading">
              <div><span>02</span><h2>What changed</h2></div>
              <p>Every value comes from the deterministic Lambda calculation.</p>
            </header>
            <MetricCards metrics={result.metrics} />
            <PerformanceChart points={result.performance_series} />
          </section>

          <section className="result-section two-column" id="method">
            <div>
              <header className="section-heading compact">
                <div><span>03</span><h2>Observable delegation</h2></div>
              </header>
              <TraceTimeline trace={result.trace} />
            </div>
            <div className="evidence-panel">
              <header className="section-heading compact">
                <div><span>04</span><h2>Controls and evidence</h2></div>
              </header>
              <div className="governance-list">
                {result.governance.map((finding) => (
                  <article key={finding.rule_id} className={finding.severity}>
                    <span>{finding.rule_id.replaceAll("_", " ")}</span>
                    <p>{finding.message}</p>
                  </article>
                ))}
              </div>
              <details open>
                <summary>Calculation assumptions</summary>
                <ul>{result.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
              </details>
              <details>
                <summary>Limitations</summary>
                <ul>{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
              </details>
              <details>
                <summary>Source objects</summary>
                <ul className="source-list">{result.data_sources.map((item) => <li key={item}>{item}</li>)}</ul>
              </details>
            </div>
          </section>
        </section>
      ) : (
        <section className="preflight">
          <div><span>02</span><h2>Ready for a real AWS run</h2></div>
          <p>
            The dashboard will populate only after the approved S3 dataset, financial Lambda,
            and Bedrock model respond. Local placeholder metrics are intentionally disabled.
          </p>
        </section>
      )}

      <footer>
        <div className="brand"><span>PG</span><div>PortfolioGuard <b>AI</b></div></div>
        <p>Simulation only · Fictional portfolios · Not financial advice · No real trades</p>
        <small>AlphaForge AI Datathon 2026 · Team 62</small>
      </footer>
    </main>
  );
}
