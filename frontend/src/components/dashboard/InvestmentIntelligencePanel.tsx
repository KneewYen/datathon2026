"use client";

import { useEffect, useRef, useState } from "react";
import {
  api,
  INVESTMENT_QUESTION,
  type AccountOption,
  type ExecutionEvent,
  type InvestmentAnalysisResponse,
} from "@/lib/api";
import { traceRows } from "@/lib/executionTrace";

const money = new Intl.NumberFormat("en-CA", {
  style: "currency",
  currency: "CAD",
  maximumFractionDigits: 0,
});

const percent = new Intl.NumberFormat("en-CA", {
  style: "percent",
  maximumFractionDigits: 1,
});

function change(
  current: number,
  proposed: number,
  format: (value: number) => string = (value) => percent.format(value),
) {
  const delta = proposed - current;
  return `${format(current)} → ${format(proposed)} (${delta >= 0 ? "+" : ""}${format(delta)})`;
}

function compatibilityStyle(value: AccountOption["compatibility"]) {
  if (value === "compatible") return "bg-emerald-100 text-emerald-800";
  if (value === "caution") return "bg-amber-100 text-amber-900";
  return "bg-red-100 text-red-800";
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-slate-200 pt-3">
      <dt className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm font-semibold text-navy">{value}</dd>
    </div>
  );
}

function AccountCard({ option }: { option: AccountOption }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.13em] text-brand-600">{option.account_type}</p>
          <h3 className="mt-1 text-lg font-semibold text-navy">{option.account_name}</h3>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">{option.objective}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-bold capitalize ${compatibilityStyle(option.compatibility)}`}>
          {option.compatibility}
        </span>
      </div>

      <dl className="mt-5 grid gap-4 sm:grid-cols-2">
        <Metric label="Covered NVIDIA exposure" value={change(option.current_nvda_exposure, option.proposed_nvda_exposure)} />
        <Metric label="Annualized volatility" value={change(option.current_volatility, option.proposed_volatility)} />
        <Metric label="Historical max drawdown" value={change(option.current_max_drawdown, option.proposed_max_drawdown)} />
        <Metric label="Concentration HHI" value={change(option.current_concentration, option.proposed_concentration, (value) => value.toFixed(3))} />
        <Metric label="NVDA / portfolio correlation" value={change(option.current_target_correlation, option.proposed_target_correlation, (value) => value.toFixed(2))} />
        <Metric label="Direct risk contribution" value={change(option.current_target_risk_contribution, option.proposed_target_risk_contribution)} />
        <Metric label="Fractional shares" value={option.shares_purchasable.toFixed(3)} />
        <Metric label="Cash after simulation" value={money.format(option.remaining_cash_cad)} />
      </dl>

      <div className="mt-5 border-t border-slate-200 pt-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Delegated strategy review</p>
        <ul className="mt-2 space-y-2">
          {option.strategy_findings.map((finding) => (
            <li key={finding.agent} className="text-xs leading-relaxed text-slate-600">
              <b className="text-navy">{finding.agent.replaceAll("_", " ")}:</b> {finding.summary}
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}

function ExecutionTrace({ events }: { events: ExecutionEvent[] }) {
  return (
    <ol className="space-y-2">
      {traceRows(events).map(({ event, depth }) => {
        return (
          <li
            key={event.event_id}
            className="rounded-md border border-slate-200 bg-white px-3 py-3"
            style={{ marginLeft: `${Math.min(depth, 3) * 18}px` }}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-brand-600">{event.kind}</span>
              <b className="text-xs text-navy">{event.agent.replaceAll("_", " ")}</b>
              {event.tool_name && <code className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px]">{event.tool_name}</code>}
              <span className={`ml-auto text-[10px] font-semibold uppercase ${event.status === "completed" ? "text-emerald-700" : "text-amber-700"}`}>
                {event.status}
              </span>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-slate-600">{event.output_summary}</p>
            {event.evidence_ids.length > 0 && (
              <p className="mt-2 break-words text-[10px] text-link">Evidence: {event.evidence_ids.join(", ")}</p>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function InvestmentIntelligencePanel({ autoRun = false }: { autoRun?: boolean }) {
  const [question, setQuestion] = useState(INVESTMENT_QUESTION);
  const [result, setResult] = useState<InvestmentAnalysisResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  async function analyze() {
    if (!question.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.investmentAnalysis(question.trim()));
    } catch (reason) {
      setResult(null);
      setError(reason instanceof Error ? reason.message : "Investment analysis failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!autoRun || started.current) return;
    started.current = true;
    void analyze();
    // The landing-page handoff should trigger once for the initial question.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRun]);

  const portfolio = result?.current_exposure;

  return (
    <section className="overflow-hidden rounded-lg bg-white ring-1 ring-slate-200">
      <div className="bg-navy px-5 py-6 text-white sm:px-6">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-300">Investment intelligence workspace</p>
            <h1 className="mt-2 text-2xl font-semibold sm:text-3xl">Compare a purchase across the whole portfolio.</h1>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">
              The orchestrator examines fictional TFSA and RRSP holdings, including covered ETF overlap, then delegates to account and strategy agents.
            </p>
          </div>
          <span className="rounded-full border border-white/20 px-3 py-1 text-xs text-slate-200">No trade execution</span>
        </div>

        <form
          className="mt-6 flex flex-col gap-3 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            void analyze();
          }}
        >
          <label className="sr-only" htmlFor="investment-question">Investment question</label>
          <input
            id="investment-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            className="min-w-0 flex-1 rounded-md bg-white px-4 py-3 text-sm text-navy outline-none ring-2 ring-transparent focus:ring-brand-400"
          />
          <button
            type="submit"
            disabled={busy || !question.trim()}
            className="rounded-md bg-brand-500 px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-600 disabled:cursor-wait disabled:opacity-60"
          >
            {busy ? "Coordinating agents…" : "Analyze purchase"}
          </button>
        </form>
      </div>

      <div className="space-y-7 p-5 sm:p-6">
        {error && (
          <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <b className="block">The analysis did not complete.</b>
            {error} No placeholder cloud result was substituted.
          </div>
        )}

        {!result && !error && (
          <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600" aria-live="polite">
            {busy
              ? "The global orchestrator is delegating to TFSA, RRSP, strategy, financial-tool, governance, and explainability components."
              : "Ready with the fictional Jordan Lee account fixture. Change the amount or account scope to test another deterministic scenario."}
          </div>
        )}

        {result?.status === "clarification_required" && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900" role="status">
            <b className="block">One detail is missing.</b>
            {result.clarification}
          </div>
        )}

        {result?.status === "completed" && (
          <div className="space-y-8" aria-live="polite">
            <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center">
              <div className="rounded-md bg-emerald-950 p-5 text-white">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-300">Grounded cross-account synthesis</p>
                <p className="mt-2 text-sm leading-relaxed text-emerald-50">{result.answer}</p>
                <p className="mt-3 text-[10px] text-emerald-200">Explanation model: {result.model_id}</p>
              </div>
              <dl className="grid grid-cols-2 gap-x-5 gap-y-3 rounded-md border border-slate-200 p-4 text-sm">
                <div><dt className="text-xs text-slate-500">Direct NVIDIA</dt><dd className="font-bold text-navy">{percent.format(portfolio?.direct_weight ?? 0)}</dd></div>
                <div><dt className="text-xs text-slate-500">ETF look-through</dt><dd className="font-bold text-navy">{percent.format(portfolio?.indirect_weight ?? 0)}</dd></div>
                <div><dt className="text-xs text-slate-500">Covered total</dt><dd className="font-bold text-navy">{money.format(portfolio?.total_exposure_cad ?? 0)}</dd></div>
                <div><dt className="text-xs text-slate-500">As analyzed</dt><dd className="font-bold text-navy">{result.intent?.currency} {result.intent?.amount.toLocaleString("en-CA")}</dd></div>
              </dl>
            </div>

            <div>
              <div className="mb-4 flex flex-wrap items-end justify-between gap-2 border-b border-navy pb-3">
                <h2 className="text-xl font-semibold">Account comparison</h2>
                <p className="text-xs text-slate-500">Historical simulation · CAD reporting · fractional shares</p>
              </div>
              <div className="grid gap-4 xl:grid-cols-2">
                {result.account_options.map((option) => <AccountCard key={option.account_id} option={option} />)}
              </div>
            </div>

            <div className="grid gap-7 xl:grid-cols-[1.15fr_0.85fr]">
              <div>
                <h2 className="border-b border-navy pb-3 text-xl font-semibold">Actual execution trace</h2>
                <p className="my-3 text-xs leading-relaxed text-slate-500">
                  These events are emitted by the completed request. Indentation follows each event&apos;s parent ID; no demo timers are used.
                </p>
                <ExecutionTrace events={result.trace} />
              </div>
              <div className="space-y-5">
                <div>
                  <h2 className="border-b border-navy pb-3 text-xl font-semibold">Governance</h2>
                  <div className="governance-list">
                    {result.governance.map((finding) => (
                      <article key={finding.rule_id} className={finding.severity}>
                        <span>{finding.rule_id.replaceAll("_", " ")}</span>
                        <p>{finding.message}</p>
                      </article>
                    ))}
                  </div>
                </div>

                <div className="rounded-md border border-amber-200 bg-amber-50 p-4">
                  <p className="text-xs font-bold uppercase tracking-[0.12em] text-amber-900">Research provider: {result.research.status}</p>
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-relaxed text-amber-900">
                    {result.research.limitations.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>

                <details className="evidence-panel" open>
                  <summary>Evidence register ({result.evidence.length})</summary>
                  <ul className="source-list">
                    {result.evidence.map((item) => (
                      <li key={item.evidence_id}><b>{item.evidence_id}</b> — {item.label} · {item.as_of}</li>
                    ))}
                  </ul>
                </details>
                <details className="evidence-panel">
                  <summary>Assumptions and limitations</summary>
                  <ul>{[...result.assumptions, ...result.limitations].map((item) => <li key={item}>{item}</li>)}</ul>
                </details>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
