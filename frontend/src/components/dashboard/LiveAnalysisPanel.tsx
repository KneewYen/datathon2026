"use client";

import { AllocationComparison } from "@/components/AllocationComparison";
import { MetricCards } from "@/components/MetricCards";
import { PerformanceChart } from "@/components/PerformanceChart";
import { TraceTimeline } from "@/components/TraceTimeline";
import {
  DEMO_QUESTION,
  type AnalysisResponse,
  type ApiMeta,
} from "@/lib/api";
import { PERSONAS, type PersonaId } from "@/lib/personas";

const CURRENT = { growth: 0.6, dividend: 0.2, momentum: 0.1, preservation: 0.1 };
const PROPOSED = { growth: 0.4, dividend: 0.4, momentum: 0.1, preservation: 0.1 };

function StatusDot({ ready, verified }: { ready: boolean; verified: boolean }) {
  const color = verified ? "bg-emerald-500" : ready ? "bg-amber-400" : "bg-slate-300";
  return <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${color}`} />;
}

export function LiveAnalysisPanel({
  personaId,
  onPersonaChange,
  result,
  busy,
  error,
  meta,
  metaError,
  onRun,
}: {
  personaId: PersonaId;
  onPersonaChange: (id: PersonaId) => void;
  result: AnalysisResponse | null;
  busy: boolean;
  error: string | null;
  meta: ApiMeta | null;
  metaError: string | null;
  onRun: () => void;
}) {
  const persona = PERSONAS.find((item) => item.id === personaId)!;
  const verified = Boolean(result);
  const services = [
    {
      name: "FastAPI",
      ready: Boolean(meta),
      verified: Boolean(meta),
      detail: meta ? "Connected" : metaError ? "Unavailable" : "Checking",
    },
    {
      name: "S3 dataset",
      ready: verified || (meta?.integrations.dataset.configured ?? false),
      verified,
      detail: verified ? "Read by Lambda" : meta?.integrations.dataset.detail ?? "Not configured",
    },
    {
      name: "Lambda tools",
      ready: verified || (meta?.integrations.lambda.configured ?? false),
      verified,
      detail: verified ? "Verified this run" : meta?.integrations.lambda.detail ?? "Not configured",
    },
    {
      name: "Bedrock",
      ready: verified || (meta?.integrations.bedrock.configured ?? false),
      verified,
      detail: verified ? "Verified this run" : meta?.integrations.bedrock.detail ?? "Not configured",
    },
  ];

  return (
    <section className="overflow-hidden rounded-lg bg-white ring-1 ring-slate-200">
      <div className="border-b border-slate-200 bg-navy px-5 py-5 text-white sm:px-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-300">
              Live AWS scenario
            </p>
            <h1 className="mt-1 max-w-3xl text-xl font-semibold leading-snug sm:text-2xl">
              {DEMO_QUESTION}
            </h1>
            <p className="mt-2 text-sm text-slate-300">
              {persona.name} · {persona.horizon} · {persona.risk} risk profile
            </p>
          </div>
          <button
            type="button"
            onClick={onRun}
            disabled={busy}
            className="shrink-0 rounded-full bg-brand-500 px-5 py-3 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-wait disabled:opacity-60"
          >
            {busy ? "Running AWS analysis…" : result ? "Run again" : "Run live analysis"}
          </button>
        </div>
      </div>

      <div className="space-y-6 p-5 sm:p-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Investor persona">
            {PERSONAS.map((item) => (
              <button
                type="button"
                key={item.id}
                onClick={() => onPersonaChange(item.id)}
                disabled={busy}
                aria-pressed={personaId === item.id}
                className={`rounded-full px-4 py-2 text-sm font-medium ring-1 transition disabled:opacity-50 ${
                  personaId === item.id
                    ? "bg-brand-500 text-white ring-brand-500"
                    : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-50"
                }`}
              >
                {item.name}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-x-5 gap-y-2 text-xs sm:grid-cols-4">
            {services.map((service) => (
              <div key={service.name} className="flex items-start gap-2">
                <StatusDot ready={service.ready} verified={service.verified} />
                <span>
                  <b className="block text-slate-700">{service.name}</b>
                  <span className="text-slate-500">{service.detail}</span>
                </span>
              </div>
            ))}
          </div>
        </div>

        {metaError && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900" role="status">
            The local API is not reachable yet: {metaError}
          </div>
        )}

        <div className="rounded-md bg-slate-50 p-4 ring-1 ring-slate-200">
          <AllocationComparison
            current={result?.current_allocations ?? CURRENT}
            proposed={result?.proposed_allocations ?? PROPOSED}
          />
        </div>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
            <b className="block">Live AWS analysis did not complete.</b>
            <span>{error}</span>
            <p className="mt-1 text-xs text-red-700">
              No placeholder metrics were substituted. Check the backend environment and temporary workshop credentials, then retry.
            </p>
          </div>
        )}

        {!result && !error && (
          <div className="rounded-md border border-slate-200 px-4 py-3 text-sm text-slate-500" aria-live="polite">
            {busy
              ? "The global orchestrator is delegating to the TFSA and strategy agents, then calling Lambda and Bedrock."
              : "Ready to run the deterministic S3-backed comparison. A successful result verifies Lambda, dataset access, governance, and Bedrock."}
          </div>
        )}

        {result && (
          <div className="space-y-8" aria-live="polite">
            <div className="rounded-md bg-emerald-950 p-5 text-white">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-300">Evidence-backed answer</p>
              <h2 className="mt-1 text-2xl font-semibold">
                {result.conclusion === "risk_reduced"
                  ? "Measured historical risk decreased."
                  : result.conclusion === "risk_increased"
                    ? "Measured historical risk increased."
                    : "The historical evidence is mixed."}
              </h2>
              <p className="mt-2 max-w-4xl text-sm leading-relaxed text-emerald-50">{result.answer}</p>
              <p className="mt-3 text-xs text-emerald-200">Bedrock: {result.model_id}</p>
            </div>

            <div>
              <div className="mb-4 flex items-end justify-between border-b border-navy pb-3">
                <h2 className="text-xl font-semibold">Deterministic metrics</h2>
                <p className="text-xs text-slate-500">Calculated by AWS Lambda</p>
              </div>
              <MetricCards metrics={result.metrics} />
              <PerformanceChart points={result.performance_series} />
            </div>

            <div className="grid gap-8 xl:grid-cols-2">
              <div>
                <h2 className="border-b border-navy pb-3 text-xl font-semibold">Observable agent delegation</h2>
                <TraceTimeline trace={result.trace} />
              </div>
              <div className="evidence-panel">
                <h2 className="border-b border-navy pb-3 text-xl font-semibold">Controls and evidence</h2>
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
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
