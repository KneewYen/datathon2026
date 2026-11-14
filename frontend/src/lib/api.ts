export type TraceStep = { agent: string; action: string };

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

export type ChatResponse = {
  answer: string;
  trace: TraceStep[];
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

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const USER_ID = "demo";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export const api = {
  chat: (message: string) => post<ChatResponse>("/api/chat", { user_id: USER_ID, message }),
  approve: (id: string, risk: string) => post<ChatResponse>(`/api/actions/${id}/approve`, { risk }),
  reject: (id: string) => post<ChatResponse>(`/api/actions/${id}/reject`, {}),
  accounts: async (): Promise<Account[]> => {
    const res = await fetch(`${API_URL}/api/accounts?user_id=${USER_ID}`);
    if (!res.ok) throw new Error(`API error ${res.status}`);
    return res.json();
  },
};
