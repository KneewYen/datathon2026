import type { PersonaId } from "./personas";

export type TraceStep = { step: string; [key: string]: unknown };

export type ChatResponse = {
  answer: string;
  metrics: Record<string, unknown>;
  trace: TraceStep[];
  warnings: string[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function sendChat(persona_id: PersonaId, message: string): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ persona_id, message }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}
