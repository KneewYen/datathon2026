export const RISK_PROFILES = [
  { id: "conservative", label: "Conservative", persona: "Robert", horizon: "Short term", level: 1 },
  { id: "balanced", label: "Balanced", persona: "Mateo", horizon: "Mid term", level: 2 },
  { id: "growth", label: "Growth", persona: "Amira", horizon: "Long term", level: 3 },
] as const;

export const RISK_LEVEL: Record<string, number> = { conservative: 1, balanced: 2, growth: 3 };

export const FAQ = [
  "I'm worried about a recession",
  "TFSA vs RRSP vs FHSA?",
  "What do interest rates mean for me?",
  "Should I hold crypto?",
  "Create a short-term account",
];
