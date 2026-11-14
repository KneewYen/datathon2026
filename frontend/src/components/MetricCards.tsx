import type { MetricEvidence } from "@/lib/api";

function formatValue(value: number, unit: MetricEvidence["unit"]) {
  if (unit === "percent") return `${(value * 100).toFixed(1)}%`;
  return value.toFixed(3);
}

export function MetricCards({ metrics }: { metrics: MetricEvidence[] }) {
  return (
    <div className="metric-grid">
      {metrics.map((metric) => {
        const favorable =
          metric.evidence_id === "metric.maximum_drawdown"
            ? metric.delta > 0
            : metric.evidence_id === "metric.annualized_return" ||
                metric.evidence_id === "metric.total_return"
              ? metric.delta > 0
              : metric.delta < 0;
        return (
          <article className="metric-card" key={metric.evidence_id}>
            <p>{metric.label}</p>
            <div className="metric-comparison">
              <span>{formatValue(metric.current, metric.unit)}</span>
              <b>→</b>
              <strong>{formatValue(metric.proposed, metric.unit)}</strong>
            </div>
            <small className={favorable ? "delta favorable" : "delta tradeoff"}>
              {metric.delta > 0 ? "+" : ""}
              {formatValue(metric.delta, metric.unit)} change
            </small>
          </article>
        );
      })}
    </div>
  );
}
