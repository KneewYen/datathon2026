import type { PersonaId } from "./personas";

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
  horizon_profile: string;
  strategies: string[];
};

export type IntegrationStatus = {
  configured: boolean;
  label: string;
  detail: string;
};

export type PersonaScenario = {
  question: string;
  account_type: "TFSA" | "RRSP";
  strategy_allocations: Record<string, number>;
  shift: { from_strategy: string; to_strategy: string; amount: number };
  portfolio_value: number;
};

export type RiskBudget = {
  max_stress_drawdown: number;
  single_position_cap: number;
  crypto_cap: number;
  max_months_underwater: number;
};

export type ApiMeta = {
  profiles: Record<string, unknown>;
  faq: string[];
  scenarios: Record<PersonaId, PersonaScenario>;
  challenge_prompts: Record<PersonaId, string[]>;
  personas: Record<
    PersonaId,
    {
      name: string;
      account_type: string;
      portfolio_value: number;
      risk_budget: RiskBudget;
      esg_excluded_sectors: string[];
    }
  >;
  strategy_labels: Record<string, string>;
  integrations: {
    region: string | null;
    lambda: IntegrationStatus;
    bedrock: IntegrationStatus;
    dataset: IntegrationStatus;
  };
};

export type MetricEvidence = {
  evidence_id: string;
  label: string;
  current: number | null;
  proposed: number | null;
  delta: number | null;
  unit: "percent" | "ratio" | "months" | "cad";
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
  status: "completed" | "blocked" | "failed";
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

export type EvidenceEntry = {
  token: string;
  evidence_id: string;
  label: string;
  role: string;
  value: number | null;
  unit: string;
  display: string;
  source: string;
  formula_version: string;
};

export type AnswerSegment = { type: "text"; text: string } | { type: "evidence"; text: string; token: string };

export type RobustnessWindow = {
  id: string;
  label: string;
  start: string;
  end: string;
  observations: number;
  conclusion: "risk_reduced" | "risk_increased" | "mixed";
};

export type StressProfile = {
  maximum_drawdown: number;
  total_return: number;
  peak_to_trough: number;
  peak_date: string | null;
  trough_date: string | null;
  recovery_date: string | null;
  months_underwater: number | null;
};

export type AnalysisResponse = {
  analysis_id: string;
  question: string;
  persona_id: PersonaId;
  account_type: "TFSA" | "RRSP";
  answer: string;
  answer_segments: AnswerSegment[];
  evidence: Record<string, EvidenceEntry>;
  conclusion: "risk_reduced" | "risk_increased" | "mixed";
  robustness: { windows?: RobustnessWindow[]; consistent?: boolean };
  stress_test: {
    window?: { id: string; label: string; start: string; end: string };
    current?: StressProfile;
    proposed?: StressProfile;
  };
  portfolio_value: number | null;
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

export type ScenarioEvidence = {
  evidence_id: string;
  label: string;
  value: number | null;
  unit: string;
  source: string;
  formula_version: string;
};

export type ChallengeScenario = {
  id: "baseline" | "requested" | "capped" | "alternative";
  label: string;
  description: string;
  strategy_allocations: Record<string, number>;
  largest_position_ticker: string;
  evidence: ScenarioEvidence[];
  recovery: Partial<StressProfile>;
  findings: GovernanceFinding[];
  within_profile: boolean;
};

export type ChallengeResponse = {
  analysis_id: string;
  persona_id: PersonaId;
  question: string;
  parsed_request: {
    ticker: string;
    name: string;
    asset_class: string;
    sector: string;
    weight: number;
    weight_source: "stated" | "stated_amount" | "assumed";
  };
  verdict: "aligned" | "cap" | "alternative" | "conflict";
  recommended_scenario: string;
  scenarios: ChallengeScenario[];
  answer: string;
  answer_segments: AnswerSegment[];
  evidence: Record<string, EvidenceEntry>;
  governance: GovernanceFinding[];
  trace: TraceStep[];
  assumptions: string[];
  limitations: string[];
  data_sources: string[];
  windows: Record<string, { start: string; end: string; label?: string }>;
  model_id: string;
  disclaimer: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const USER_ID = "demo";

export const DEMO_QUESTION =
  "Would moving 20% of my TFSA from my tech-heavy growth strategy into a broad index strategy diversify me without abandoning growth?";

async function liveRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail ? `: ${payload.detail}` : "";
    throw new Error(`Live AWS analysis unavailable (${response.status})${detail}`);
  }
  return response.json();
}

export function runAnalysis(persona_id: PersonaId): Promise<AnalysisResponse> {
  return liveRequest<AnalysisResponse>(`/api/analysis/persona/${persona_id}`);
}

export function runChallenge(persona_id: PersonaId, message: string): Promise<ChallengeResponse> {
  return liveRequest<ChallengeResponse>("/api/challenge", { persona_id, message });
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  const response = await fetch(`${API_URL}${path}`);
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
};
