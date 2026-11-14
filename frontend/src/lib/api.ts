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

export async function runAnalysis(persona_id: PersonaId): Promise<AnalysisResponse> {
  const response = await fetch(`${API_URL}/api/analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
