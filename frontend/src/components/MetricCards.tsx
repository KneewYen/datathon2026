import type { MetricEvidence } from "@/lib/api";
import { formatValue } from "@/lib/format";

const HIGHER_IS_BETTER = new Set([
  "metric.maximum_drawdown",
  "metric.annualized_return",
  "metric.total_return",
  "metric.stress_2022_drawdown",
  "metric.stress_2022_return",
  "metric.stress_2022_loss_cad",
  "metric.full_history_drawdown",
]);

export function MetricCards({ metrics }: { metrics: MetricEvidence[] }) {
  return (
    <div className="metric-grid">
      {metrics.map((metric) => {
        const delta = metric.delta;
        const favorable = delta === null ? null : HIGHER_IS_BETTER.has(metric.evidence_id) ? delta > 0 : delta < 0;
        return (
          <article className="metric-card" key={metric.evidence_id}>
            <p>{metric.label}</p>
            <div className="metric-comparison">
              <span>{formatValue(metric.current, metric.unit)}</span>
              <b>→</b>
              <strong>{formatValue(metric.proposed, metric.unit)}</strong>
            </div>
            <small className={favorable === null ? "delta" : favorable ? "delta favorable" : "delta tradeoff"}>
              {delta === null ? "recovery not observed" : `${formatValue(delta, metric.unit, true)} change`}
            </small>
          </article>
        );
      })}
    </div>
  );
}
