export type PersonaId = "amira" | "mateo" | "robert";

export type Persona = {
  id: PersonaId;
  name: string;
  age: number;
  horizon: string;
  horizonAgent: string;
  risk: string;
  goal: string;
  strategies: string[];
  prompts: string[];
};

export const PERSONAS: Persona[] = [
  {
    id: "amira",
    name: "Amira",
    age: 26,
    horizon: "15+ years",
    horizonAgent: "Long-Term",
    risk: "High",
    goal: "Long-term growth, still diversified",
    strategies: ["Growth", "Crypto", "Momentum"],
    prompts: [
      "How much crypto fits my profile?",
      "Am I too concentrated in tech?",
    ],
  },
  {
    id: "mateo",
    name: "Mateo",
    age: 41,
    horizon: "8–12 years",
    horizonAgent: "Mid-Term",
    risk: "Moderate",
    goal: "Balanced growth with ESG",
    strategies: ["ESG", "Dividend", "Balanced Index"],
    prompts: [
      "Compare ESGV with SPY for me.",
      "Should I hold energy stocks?",
    ],
  },
  {
    id: "robert",
    name: "Robert",
    age: 59,
    horizon: "3–5 years",
    horizonAgent: "Short-Term",
    risk: "Low–moderate",
    goal: "Preserve capital, some growth",
    strategies: ["Preservation", "Bond", "Quality"],
    prompts: [
      "Should I buy NVDA now?",
      "How safe is my bond allocation?",
    ],
  },
];
