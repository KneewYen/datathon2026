import type { PerformancePoint } from "@/lib/api";

const WIDTH = 760;
const HEIGHT = 250;
const PAD = 28;

function pathFor(values: number[], min: number, max: number) {
  const range = max - min || 1;
  return values
    .map((value, index) => {
      const x = PAD + (index / Math.max(1, values.length - 1)) * (WIDTH - PAD * 2);
      const y = HEIGHT - PAD - ((value - min) / range) * (HEIGHT - PAD * 2);
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export function PerformanceChart({ points }: { points: PerformancePoint[] }) {
  if (points.length < 2) return null;
  const current = points.map((point) => point.current);
  const proposed = points.map((point) => point.proposed);
  const min = Math.min(0, ...current, ...proposed);
  const max = Math.max(0, ...current, ...proposed);
  const zeroY = HEIGHT - PAD - ((0 - min) / (max - min || 1)) * (HEIGHT - PAD * 2);
  return (
    <div className="chart-wrap">
      <div className="chart-heading">
        <div>
          <span className="eyebrow">Historical comparison</span>
          <h3>Cumulative CAD return</h3>
        </div>
        <div className="legend">
          <span><i className="current-line" />Current</span>
          <span><i className="proposed-line" />Proposed</span>
        </div>
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Current and proposed historical cumulative return">
        <line x1={PAD} x2={WIDTH - PAD} y1={zeroY} y2={zeroY} className="zero-line" />
        <path d={pathFor(current, min, max)} className="chart-current" />
        <path d={pathFor(proposed, min, max)} className="chart-proposed" />
      </svg>
      <div className="chart-dates">
        <span>{points[0].date}</span>
        <span>{points.at(-1)?.date}</span>
      </div>
    </div>
  );
}
