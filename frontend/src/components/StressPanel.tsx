import type { AnalysisResponse, RiskBudget } from "@/lib/api";
import { formatValue } from "@/lib/format";

const CONCLUSION_TEXT: Record<string, string> = {
  risk_reduced: "risk reduced",
  risk_increased: "risk increased",
  mixed: "mixed evidence",
};

function LossBar({ label, value, budget }: { label: string; value: number | null; budget?: number }) {
  const scale = Math.max(Math.abs(budget ?? 0), Math.abs(value ?? 0), 0.01) * 1.15;
  const width = value === null ? 0 : (Math.abs(value) / scale) * 100;
  const over = budget !== undefined && value !== null && value < budget;
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-600">
        <span>{label}</span>
        <b className={over ? "text-red-700" : "text-slate-800"}>{formatValue(value, "percent")}</b>
      </div>
      <div className="relative mt-1 h-2.5 rounded-full bg-slate-100">
        <div className={`h-2.5 rounded-full ${over ? "bg-red-500" : "bg-navy"}`} style={{ width: `${width}%` }} />
        {budget !== undefined && (
          <div
            className="absolute -top-1 h-4.5 w-0.5 bg-amber-500"
            style={{ left: `${(Math.abs(budget) / scale) * 100}%` }}
            title={`Loss budget ${formatValue(budget, "percent")}`}
          />
        )}
      </div>
    </div>
  );
}

export function StressPanel({
  result,
  budget,
  personaName,
}: {
  result: AnalysisResponse;
  budget?: RiskBudget;
  personaName: string;
}) {
  const metric = (id: string) => result.metrics.find((item) => item.evidence_id === id);
  const stress = metric("metric.stress_2022_drawdown");
  const loss = metric("metric.stress_2022_loss_cad");
  const months = metric("metric.months_underwater");
  const windows = result.robustness.windows ?? [];
  const consistent = result.robustness.consistent;
  if (!stress) return null;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="rounded-md p-4 ring-1 ring-slate-200">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-brand-500">Stress replay</p>
        <h3 className="mt-1 text-lg font-semibold">What if 2022 happened again?</h3>
        <p className="mt-1 text-xs text-slate-500">
          {result.stress_test.window?.label} ({result.stress_test.window?.start} to {result.stress_test.window?.end}),
          when stocks and bonds fell together. Amber line: {personaName}&apos;s loss budget.
        </p>
        <div className="mt-4 space-y-3">
          <LossBar label="Current portfolio" value={stress.current} budget={budget?.max_stress_drawdown} />
          <LossBar label="Proposed portfolio" value={stress.proposed} budget={budget?.max_stress_drawdown} />
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
          {loss && (
            <div className="rounded bg-slate-50 p-2">
              <dt className="text-slate-500">Loss on fictional balance</dt>
              <dd className="font-semibold">
                {formatValue(loss.current, "cad")} → {formatValue(loss.proposed, "cad")}
              </dd>
            </div>
          )}
          {months && (
            <div className="rounded bg-slate-50 p-2">
              <dt className="text-slate-500">Months to recover (budget {budget?.max_months_underwater ?? "?"})</dt>
              <dd className="font-semibold">
                {formatValue(months.current, "months")} → {formatValue(months.proposed, "months")}
              </dd>
            </div>
          )}
        </dl>
      </div>

      <div className="rounded-md p-4 ring-1 ring-slate-200">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-brand-500">Sensitivity</p>
        <h3 className="mt-1 flex items-center gap-2 text-lg font-semibold">
          Does the conclusion hold?
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              consistent ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-900"
            }`}
          >
            {consistent ? "Robust" : "Window-sensitive"}
          </span>
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          The same comparison is re-run on a second window that includes the 2022 selloff.
        </p>
        <ul className="mt-4 space-y-2 text-sm">
          {windows.map((window) => (
            <li key={window.id} className="flex items-center justify-between rounded bg-slate-50 px-3 py-2">
              <span>
                <b className="block text-xs">{window.label}</b>
                <span className="text-xs text-slate-500">
                  {window.start} to {window.end} · {window.observations} observations
                </span>
              </span>
              <span className="text-xs font-semibold">{CONCLUSION_TEXT[window.conclusion]}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
