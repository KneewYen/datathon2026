import { strategyColor, strategyLabel } from "@/lib/format";

function AllocationColumn({
  title,
  allocations,
  accountType,
}: {
  title: string;
  allocations: Record<string, number>;
  accountType: string;
}) {
  const entries = Object.entries(allocations).filter(([, weight]) => weight > 1e-9);
  return (
    <div className="allocation-column">
      <div className="allocation-title-row">
        <h3>{title}</h3>
        <span>{accountType}</span>
      </div>
      <div className="allocation-stack" aria-label={`${title} strategy allocation`}>
        {entries.map(([strategy, weight]) => (
          <div
            key={strategy}
            style={{ width: `${weight * 100}%`, background: strategyColor(strategy) }}
            title={`${strategyLabel(strategy)} ${(weight * 100).toFixed(0)}%`}
          />
        ))}
      </div>
      <dl className="allocation-list">
        {entries.map(([strategy, weight]) => (
          <div key={strategy}>
            <dt>
              <i style={{ background: strategyColor(strategy) }} />
              {strategyLabel(strategy)}
            </dt>
            <dd>{(weight * 100).toFixed(0)}%</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function AllocationComparison({
  current,
  proposed,
  shiftAmount = 0.2,
  accountType = "TFSA",
}: {
  current: Record<string, number>;
  proposed: Record<string, number>;
  shiftAmount?: number;
  accountType?: string;
}) {
  const points = Math.round(shiftAmount * 100);
  return (
    <div className="allocation-grid">
      <AllocationColumn title="Current allocation" allocations={current} accountType={accountType} />
      <div className="shift-marker" aria-label={`Move ${points} percentage points`}>
        <span>{points} pts</span>
        <b>→</b>
      </div>
      <AllocationColumn title="Proposed allocation" allocations={proposed} accountType={accountType} />
    </div>
  );
}

export function applyShift(
  allocations: Record<string, number>,
  shift: { from_strategy: string; to_strategy: string; amount: number },
): Record<string, number> {
  return {
    ...allocations,
    [shift.from_strategy]: (allocations[shift.from_strategy] ?? 0) - shift.amount,
    [shift.to_strategy]: (allocations[shift.to_strategy] ?? 0) + shift.amount,
  };
}