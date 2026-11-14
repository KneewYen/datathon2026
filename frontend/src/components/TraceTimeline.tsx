import type { TraceStep } from "@/lib/api";
import type { CSSProperties } from "react";

const AGENT_NAMES: Record<string, string> = {
  global_orchestrator: "Global orchestrator",
  tfsa_account_agent: "TFSA account agent",
  rrsp_account_agent: "RRSP account agent",
  growth_strategy_agent: "Growth strategy agent",
  dividend_strategy_agent: "Dividend strategy agent",
  momentum_strategy_agent: "Momentum strategy agent",
  capital_preservation_strategy_agent: "Capital preservation agent",
  aws_financial_tools: "AWS financial tools",
  governance_agent: "Governance",
  explainability_agent: "Explainability",
};

export function TraceTimeline({ trace }: { trace: TraceStep[] }) {
  return (
    <ol className="trace-list">
      {trace.map((step, index) => (
        <li key={step.step_id} style={{ "--depth": step.parent_id ? 1 : 0 } as CSSProperties}>
          <span className="trace-number">{String(index + 1).padStart(2, "0")}</span>
          <div>
            <div className="trace-agent">
              {AGENT_NAMES[step.agent] ?? step.agent}
              <span>{step.status}</span>
            </div>
            <p>{step.action}</p>
            {step.delegated_to.length > 0 && (
              <small>Delegated to {step.delegated_to.map((agent) => AGENT_NAMES[agent] ?? agent).join(", ")}</small>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
