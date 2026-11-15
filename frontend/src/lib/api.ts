import { getLang, translate } from "@/i18n";
import { PERSONAS, type PersonaId } from "./personas";

export type Proposal = {
  id: string;
  type: "create_account";
  account_type: string;
  account_type_label?: string;
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
  balance: number;
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

export type TradeAction = "buy" | "sell";

export type TradeVerdict =
  | "no_signal"
  | "panic_risk"
  | "evidence_supported"
  | "mixed"
  | "chasing_risk"
  | "falling_knife"
  | "dip_with_context";

export type Holding = {
  ticker: string;
  weight: number;
  shares: number;
  price: number;
  value_cad: number;
  move_pct: number;
};

export type Portfolio = {
  persona_id: PersonaId;
  refreshed: boolean;
  invested_cad: number;
  cash_cad: number;
  total_value_cad: number;
  holdings: Holding[];
  note: string;
  computed_by: string;
};

export type MarketStatus = {
  refreshed: boolean;
  new_price_rows: number;
  new_headlines: number;
  computed_by: string;
};

export type TradeCheck = {
  action: TradeAction;
  ticker: string;
  verdict: TradeVerdict;
  score: { name: string; value: number; low_label: string; high_label: string } | null;
  sentiment: number | null;
  sentiment_label: "upbeat" | "neutral" | "negative" | null;
  evidence: { evidence_id: string; label: string; value: number | null; unit: string }[];
  limitations: string[];
  computed_by: string;
};

export async function runAnalysis(persona_id: PersonaId): Promise<AnalysisResponse> {
  const persona = PERSONAS.find((item) => item.id === persona_id)!;
  const response = await fetch(`${API_URL}/api/analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      persona_id,
      question: translate(`persona.${persona_id}.scenario`),
      language: getLang(),
      account_type: "TFSA",
      strategy_allocations: persona.allocations,
      shift: { from_strategy: persona.scenario.from, to_strategy: persona.scenario.to, amount: persona.scenario.amount },
    }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail ? `: ${body.detail}` : "";
    console.error("analysis failed", response.status, detail);
    throw new Error(translate("error.analysis", { status: response.status }));
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
    console.error("request failed", response.status, detail);
    throw new Error(translate("error.generic", { status: response.status }));
  }
  return response.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail ? `: ${payload.detail}` : "";
    console.error("request failed", response.status, detail);
    throw new Error(translate("error.generic", { status: response.status }));
  }
  return response.json();
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail ? `: ${payload.detail}` : "";
    console.error("request failed", response.status, detail);
    throw new Error(translate("error.generic", { status: response.status }));
  }
  return response.json();
}

export const api = {
  chat: (message: string) => post<ChatResponse>("/api/chat", { user_id: USER_ID, message, lang: getLang() }),
  approve: (id: string, risk: string | undefined) => post<ChatResponse>(`/api/actions/${id}/approve`, { risk, lang: getLang() }),
  reject: (id: string) => post<ChatResponse>(`/api/actions/${id}/reject?lang=${getLang()}`, {}),
  accounts: () => get<Account[]>(`/api/accounts?user_id=${encodeURIComponent(USER_ID)}`),
  deleteAccount: async (id: string) => {
    const response = await fetch(`${API_URL}/api/accounts/${id}?user_id=${encodeURIComponent(USER_ID)}`, { method: "DELETE" });
    if (!response.ok) throw new Error(translate("error.removeAccount", { status: response.status }));
  },
  market: () => get<MarketStatus>("/api/market"),
  refreshMarket: () => post<MarketStatus>("/api/market/refresh", {}),
  resetMarket: () => post<MarketStatus>("/api/market/reset", {}),
  portfolio: (persona: PersonaId) => get<Portfolio>(`/api/portfolio/${persona}`),
  tradeCheck: (ticker: string, action: TradeAction) =>
    get<TradeCheck>(`/api/trade-check/${encodeURIComponent(ticker)}?action=${action}`),
  features: () => get<{ flags: Record<string, boolean> }>("/api/features"),
  setFeature: (id: string, enabled: boolean) =>
    put<{ flags: Record<string, boolean> }>(`/api/features/${id}`, { enabled }),
  resetFeatures: () => post<{ flags: Record<string, boolean> }>("/api/features/reset", {}),
  meta: () => get<ApiMeta>("/api/meta"),
};
