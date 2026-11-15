import type { PersonaId } from "./personas";
import { apiAuthorizationHeader } from "./auth";

export type Proposal = {
  id: string;
  type: "create_account";
  account_type: string;
  horizon: string;
  horizon_label: string;
  risk: string;
  risk_label: string;
  persona: string;
  reason: string;
};

export type ChatMessage = {
  role: "user" | "assistant";
  text?: string;
  data?: ChatResponse;
  resolved?: boolean;
};

export type ChatResponse = {
  answer: string;
  trace: Array<{ agent: string; action: string }>;
  metrics: Record<string, string>;
  sources: string[];
  warnings: string[];
  proposal: Proposal | null;
  suggestions: string[];
};

export type Account = {
  id: string;
  name: string;
  type: string;
  horizon: string;
  risk: string;
  risk_label: string;
  persona: string;
  horizon_agent: string;
  strategies: string[];
};

export type IntegrationStatus = {
  configured: boolean;
  label: string;
  detail: string;
};

export type ApiMeta = {
  profiles: Record<string, unknown>;
  faq: string[];
  integrations: {
    region: string | null;
    lambda: IntegrationStatus;
    bedrock: IntegrationStatus;
    dataset: IntegrationStatus;
    orchestration: IntegrationStatus;
  };
};

export type MetricEvidence = {
  evidence_id: string;
  label: string;
  current: number;
  proposed: number;
  delta: number;
  unit: "percent" | "ratio";
  source: string;
  formula_version: string;
};

export type PerformancePoint = {
  date: string;
  current: number;
  proposed: number;
};

export type TraceStep = {
  step_id: string;
  parent_id: string | null;
  agent: string;
  action: string;
  status: "running" | "completed" | "blocked" | "failed";
  delegated_to: string[];
  evidence_ids: string[];
  details: Record<string, unknown>;
};

export type GovernanceFinding = {
  rule_id: string;
  severity: "info" | "warning" | "block";
  message: string;
  evidence_ids: string[];
};

export type AgentFinding = {
  agent: string;
  role: string;
  summary: string;
  requested_operations: string[];
  evidence_ids: string[];
};

export type InvestmentIntent = {
  operation: "buy";
  ticker: string;
  amount: number;
  currency: "CAD" | "USD";
  account_ids: string[];
  compare_accounts: boolean;
};

export type EvidenceRecord = {
  evidence_id: string;
  category: "calculation" | "market" | "holdings" | "research" | "governance";
  label: string;
  value: number | string;
  unit: string;
  source: string;
  as_of: string;
  details: Record<string, unknown>;
};

export type ExecutionEvent = {
  event_id: string;
  parent_id: string | null;
  request_id: string;
  kind: "orchestrator" | "agent" | "tool" | "governance" | "explainability";
  agent: string;
  tool_name: string | null;
  started_at: string;
  ended_at: string;
  status: "completed" | "blocked" | "failed";
  evidence_ids: string[];
  input_summary: string;
  output_summary: string;
  error: string | null;
};

export type AccountOption = {
  account_id: string;
  account_type: "TFSA" | "RRSP";
  account_name: string;
  objective: string;
  risk_tolerance: string;
  compatibility: "compatible" | "caution" | "conflict" | "blocked";
  shares_purchasable: number;
  purchase_price_cad: number;
  remaining_cash_cad: number;
  current_nvda_exposure: number;
  proposed_nvda_exposure: number;
  portfolio_current_nvda_exposure: number;
  portfolio_proposed_nvda_exposure: number;
  current_volatility: number;
  proposed_volatility: number;
  current_max_drawdown: number;
  proposed_max_drawdown: number;
  current_concentration: number;
  proposed_concentration: number;
  current_target_correlation: number;
  proposed_target_correlation: number;
  current_target_risk_contribution: number;
  proposed_target_risk_contribution: number;
  evidence_ids: string[];
  strategy_findings: AgentFinding[];
};

export type ResearchResult = {
  status: "available" | "unavailable" | "failed";
  provider: string;
  retrieved_at: string;
  items: Array<Record<string, unknown>>;
  limitations: string[];
};

export type InvestmentAnalysisResponse = {
  request_id: string;
  status: "completed" | "clarification_required";
  question: string;
  clarification: string | null;
  intent: InvestmentIntent | null;
  investor: Record<string, unknown>;
  accounts: Array<Record<string, unknown>>;
  current_exposure: Record<string, number>;
  account_options: AccountOption[];
  governance: GovernanceFinding[];
  research: ResearchResult;
  evidence: EvidenceRecord[];
  trace: ExecutionEvent[];
  answer: string;
  assumptions: string[];
  limitations: string[];
  model_id: string;
  disclaimer: string;
};

export type WorkflowStartResponse = {
  request_id: string;
  execution_arn: string;
  status: "RUNNING";
  mode: "aws_step_functions";
};

export type WorkflowStatusResponse = {
  request_id: string;
  execution_arn: string;
  status:
    | "RUNNING"
    | "SUCCEEDED"
    | "FAILED"
    | "TIMED_OUT"
    | "ABORTED"
    | "PENDING_REDRIVE";
  events: ExecutionEvent[];
  result: InvestmentAnalysisResponse | null;
  error: string | null;
};

export type AnalysisResponse = {
  analysis_id: string;
  question: string;
  persona_id: PersonaId;
  account_type: "TFSA" | "RRSP";
  answer: string;
  conclusion: "risk_reduced" | "risk_increased" | "mixed";
  current_allocations: Record<string, number>;
  proposed_allocations: Record<string, number>;
  metrics: MetricEvidence[];
  performance_series: PerformancePoint[];
  agent_findings: AgentFinding[];
  governance: GovernanceFinding[];
  trace: TraceStep[];
  assumptions: string[];
  limitations: string[];
  data_sources: string[];
  model_id: string;
  disclaimer: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const USER_ID = "demo";

export const DEMO_QUESTION =
  "Would moving 20% of my TFSA from my growth strategy into my dividend strategy reduce my risk?";

export const INVESTMENT_QUESTION =
  "I am considering buying $5,000 CAD of NVIDIA. Which account is a better fit, my TFSA or RRSP?";

export async function runAnalysis(persona_id: PersonaId): Promise<AnalysisResponse> {
  const response = await fetch(`${API_URL}/api/analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...apiAuthorizationHeader() },
    body: JSON.stringify({
      persona_id,
      question: DEMO_QUESTION,
      account_type: "TFSA",
    }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail ? `: ${body.detail}` : "";
    throw new Error(`Live AWS analysis unavailable (${response.status})${detail}`);
  }
  return response.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...apiAuthorizationHeader() },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail ? `: ${payload.detail}` : "";
    throw new Error(`API request failed (${response.status})${detail}`);
  }
  return response.json();
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: apiAuthorizationHeader(),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail ? `: ${payload.detail}` : "";
    throw new Error(`API request failed (${response.status})${detail}`);
  }
  return response.json();
}

export const api = {
  chat: (message: string) => post<ChatResponse>("/api/chat", { user_id: USER_ID, message }),
  approve: (id: string, risk: string | undefined) => post<ChatResponse>(`/api/actions/${id}/approve`, { risk }),
  reject: (id: string) => post<ChatResponse>(`/api/actions/${id}/reject`, {}),
  accounts: () => get<Account[]>(`/api/accounts?user_id=${encodeURIComponent(USER_ID)}`),
  meta: () => get<ApiMeta>("/api/meta"),
  investmentAnalysis: (question: string) =>
    post<InvestmentAnalysisResponse | WorkflowStartResponse>(
      "/api/investment-analysis",
      { question },
    ),
  investmentAnalysisStatus: (requestId: string) =>
    get<WorkflowStatusResponse>(
      `/api/investment-analysis/executions/${encodeURIComponent(requestId)}`,
    ),
};
