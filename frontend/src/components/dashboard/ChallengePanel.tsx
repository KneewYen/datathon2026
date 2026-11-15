"use client";

import { useState } from "react";
import { EvidenceAnswer } from "@/components/EvidenceAnswer";
import { TraceTimeline } from "@/components/TraceTimeline";
import { runChallenge, type ChallengeResponse, type ChallengeScenario } from "@/lib/api";
import { formatValue } from "@/lib/format";
import { PERSONAS, type PersonaId } from "@/lib/personas";

const VERDICT: Record<ChallengeResponse["verdict"], { title: string; tone: string }> = {
  aligned: { title: "Fits the profile as requested", tone: "bg-emerald-950 text-white" },
  cap: { title: "Not as requested: a smaller position fits", tone: "bg-amber-900 text-white" },
  alternative: { title: "Not as requested: a diversified alternative fits", tone: "bg-amber-900 text-white" },
  conflict: { title: "Conflicts with the profile: keep the current portfolio", tone: "bg-red-900 text-white" },
};

const COLUMNS: Array<{ key: string; label: string; higherIsBetter: boolean }> = [
  { key: "focus_position", label: "Requested asset weight", higherIsBetter: false },
  { key: "stress_2022_drawdown", label: "2022 replay loss", higherIsBetter: true },
  { key: "stress_2022_loss_cad", label: "2022 loss on balance", higherIsBetter: true },
  { key: "months_underwater", label: "Months to recover", higherIsBetter: false },
  { key: "annualized_volatility", label: "Volatility", higherIsBetter: false },
  { key: "annualized_return", label: "Hist. annual return", higherIsBetter: true },
];

function value(scenario: ChallengeScenario, key: string) {
  return scenario.evidence.find((item) => item.evidence_id.endsWith(`.${key}`));
}

export function ChallengePanel({
  personaId,
  prompts,
}: {
  personaId: PersonaId;
  prompts: string[];
}) {
  const persona = PERSONAS.find((item) => item.id === personaId)!;
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ChallengeResponse | null>(null);

  const submit = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setMessage(trimmed);
    setBusy(true);
    setError(null);
    try {
      setResult(await runChallenge(personaId, trimmed));
    } catch (reason) {
      setResult(null);
      setError(reason instanceof Error ? reason.message : "Challenge failed");
    } finally {
      setBusy(false);
    }
  };

  const current = result && result.persona_id === personaId ? result : null;

  return (
    <section className="overflow-hidden rounded-lg bg-white ring-1 ring-slate-200">
      <div className="border-b border-slate-200 bg-navy px-5 py-5 text-white sm:px-6">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-300">Suitability challenge</p>
        <h2 className="mt-1 text-xl font-semibold sm:text-2xl">
          Ask for something specific. {persona.name}&apos;s advisor will push back if it doesn&apos;t fit.
        </h2>
        <p className="mt-2 text-sm text-slate-300">
          The request is measured as asked, capped, and as a diversified alternative, all on the same AWS data.
        </p>
      </div>

      <div className="space-y-5 p-5 sm:p-6">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submit(message);
          }}
          className="flex flex-col gap-2 sm:flex-row"
        >
          <input
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder={`e.g. ${prompts[0] ?? "Put 25% in NVDA"}`}
            className="flex-1 rounded-full bg-white px-5 py-3 outline-none ring-1 ring-slate-300 focus:ring-2 focus:ring-navy"
          />
          <button
            disabled={busy || !message.trim()}
            className="rounded-full bg-brand-500 px-6 py-3 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:opacity-40"
          >
            {busy ? "Testing in AWS…" : "Challenge it"}
          </button>
        </form>
        <div className="flex flex-wrap gap-2">
          {prompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              disabled={busy}
              onClick={() => void submit(prompt)}
              className="rounded-full bg-white px-3 py-1 text-sm text-link ring-1 ring-slate-300 hover:bg-slate-50 disabled:opacity-40"
            >
              {prompt}
            </button>
          ))}
        </div>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
            {error}
          </div>
        )}

        {current && (
          <div className="space-y-6" aria-live="polite">
            <div className={`rounded-md p-5 ${VERDICT[current.verdict].tone}`}>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] opacity-80">
                {current.parsed_request.name} ({current.parsed_request.ticker}) ·{" "}
                {formatValue(current.parsed_request.weight, "percent")}{" "}
                {current.parsed_request.weight_source === "assumed" ? "assumed size" : "requested"}
              </p>
              <h3 className="mt-1 text-2xl font-semibold">{VERDICT[current.verdict].title}</h3>
              <div className="mt-3">
                <EvidenceAnswer
                  segments={current.answer_segments}
                  evidence={current.evidence}
                  fallback={current.answer}
                />
              </div>
              <p className="mt-3 text-xs opacity-70">Bedrock: {current.model_id}</p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead>
                  <tr className="border-b border-navy text-[11px] uppercase tracking-wide text-slate-500">
                    <th className="py-2 pr-3">Scenario</th>
                    {COLUMNS.map((column) => (
                      <th key={column.key} className="px-2 py-2 text-right">
                        {column.label}
                      </th>
                    ))}
                    <th className="px-2 py-2">Profile check</th>
                  </tr>
                </thead>
                <tbody>
                  {current.scenarios.map((scenario) => {
                    const recommended = scenario.id === current.recommended_scenario;
                    return (
                      <tr
                        key={scenario.id}
                        className={`border-b border-slate-200 align-top ${recommended ? "bg-emerald-50" : ""}`}
                      >
                        <td className="py-3 pr-3">
                          <b className="block">
                            {scenario.label}
                            {recommended && (
                              <span className="ml-2 rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-semibold uppercase text-white">
                                Recommended
                              </span>
                            )}
                          </b>
                          <span className="text-xs text-slate-500">{scenario.description}</span>
                        </td>
                        {COLUMNS.map((column) => {
                          const item = value(scenario, column.key);
                          return (
                            <td key={column.key} className="px-2 py-3 text-right font-mono text-xs">
                              {item ? formatValue(item.value, item.unit) : "—"}
                            </td>
                          );
                        })}
                        <td className="px-2 py-3 text-xs">
                          {scenario.findings.length === 0 ? (
                            <span className="font-semibold text-emerald-700">Within budget</span>
                          ) : (
                            <ul className="space-y-1">
                              {scenario.findings.map((finding) => (
                                <li key={finding.rule_id} title={finding.message}>
                                  <span
                                    className={
                                      finding.rule_id === "STRESS_BUDGET_NEAR_LIMIT"
                                        ? "font-semibold text-amber-700"
                                        : "font-semibold text-red-700"
                                    }
                                  >
                                    {finding.rule_id.replaceAll("_", " ").toLowerCase()}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-slate-500">
                Hover a profile check for the rule&apos;s reasoning. All figures are historical observations from AWS Lambda.
              </p>
            </div>

            <div className="grid gap-8 xl:grid-cols-2">
              <div>
                <h3 className="border-b border-navy pb-3 text-lg font-semibold">Observable agent steps</h3>
                <TraceTimeline trace={current.trace} />
              </div>
              <div className="evidence-panel">
                <h3 className="border-b border-navy pb-3 text-lg font-semibold">Controls and evidence</h3>
                <div className="governance-list">
                  {current.governance.map((finding) => (
                    <article key={finding.rule_id} className={finding.severity}>
                      <span>{finding.rule_id.replaceAll("_", " ")}</span>
                      <p>{finding.message}</p>
                    </article>
                  ))}
                  {current.scenarios
                    .filter((scenario) => scenario.id === "requested")
                    .flatMap((scenario) => scenario.findings)
                    .map((finding) => (
                      <article key={`requested-${finding.rule_id}`} className={finding.severity}>
                        <span>Requested · {finding.rule_id.replaceAll("_", " ")}</span>
                        <p>{finding.message}</p>
                      </article>
                    ))}
                </div>
                <details>
                  <summary>Calculation assumptions</summary>
                  <ul>{current.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
                </details>
                <details>
                  <summary>Limitations</summary>
                  <ul>{current.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
                </details>
                <details>
                  <summary>Source objects</summary>
                  <ul className="source-list">{current.data_sources.map((item) => <li key={item}>{item}</li>)}</ul>
                </details>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
