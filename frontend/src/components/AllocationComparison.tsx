const STRATEGY_LABELS: Record<string, string> = {
  growth: "Growth",
  dividend: "Dividend",
  momentum: "Momentum",
  preservation: "Capital preservation",
};

const STRATEGY_COLORS: Record<string, string> = {
  growth: "var(--coral)",
  dividend: "var(--blue)",
  momentum: "var(--gold)",
  preservation: "var(--sage)",
};

function AllocationColumn({
  title,
  allocations,
}: {
  title: string;
  allocations: Record<string, number>;
}) {
  return (
    <div className="allocation-column">
      <div className="allocation-title-row">
        <h3>{title}</h3>
        <span>TFSA</span>
      </div>
      <div className="allocation-stack" aria-label={`${title} strategy allocation`}>
        {Object.entries(allocations).map(([strategy, weight]) => (
          <div
            key={strategy}
            style={{ width: `${weight * 100}%`, background: STRATEGY_COLORS[strategy] }}
            title={`${STRATEGY_LABELS[strategy]} ${(weight * 100).toFixed(0)}%`}
          />
        ))}
      </div>
      <dl className="allocation-list">
        {Object.entries(allocations).map(([strategy, weight]) => (
          <div key={strategy}>
            <dt>
              <i style={{ background: STRATEGY_COLORS[strategy] }} />
              {STRATEGY_LABELS[strategy]}
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
}: {
  current: Record<string, number>;
  proposed: Record<string, number>;
}) {
  return (
    <div className="allocation-grid">
      <AllocationColumn title="Current allocation" allocations={current} />
      <div className="shift-marker" aria-label="Move 20 percentage points">
        <span>20 pts</span>
        <b>→</b>
      </div>
      <AllocationColumn title="Proposed allocation" allocations={proposed} />
    </div>
  );
}
