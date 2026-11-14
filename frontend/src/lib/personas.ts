export type PersonaId = "amira" | "mateo" | "robert";

export type StrategyKey = "growth" | "dividend" | "momentum" | "preservation";

export type Scenario = { from: StrategyKey; to: StrategyKey; amount: number; question: string };

export type Persona = {
  id: PersonaId;
  name: string;
  age: number;
  horizon: string;
  horizonAgent: string;
  risk: string;
  goal: string;
  strategies: string[];
  startingBalance: number; // CAD
  allocations: Record<StrategyKey, number>;
  scenario: Scenario;
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
    startingBalance: 15000,
    allocations: { growth: 0.55, dividend: 0.10, momentum: 0.25, preservation: 0.10 },
    scenario: { from: "growth", to: "dividend", amount: 0.2, question: "Would moving 20% of my TFSA from my growth strategy into my dividend strategy reduce my risk?" },
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
    startingBalance: 60000,
    allocations: { growth: 0.30, dividend: 0.35, momentum: 0.10, preservation: 0.25 },
    scenario: { from: "growth", to: "preservation", amount: 0.1, question: "Would moving 10% of my TFSA from my growth strategy into my preservation strategy reduce my risk?" },
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
    startingBalance: 150000,
    allocations: { growth: 0.15, dividend: 0.30, momentum: 0.05, preservation: 0.50 },
    scenario: { from: "dividend", to: "preservation", amount: 0.1, question: "Would moving 10% of my TFSA from my dividend strategy into my preservation strategy reduce my risk?" },
    prompts: [
      "Should I buy NVDA now?",
      "How safe is my bond allocation?",
    ],
  },
];

export const formatCad = (amount: number) =>
  new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 0 }).format(amount);

export const allocationLabel = (allocations: Persona["allocations"]) =>
  Object.entries(allocations)
    .sort((a, b) => b[1] - a[1])
    .map(([name, weight]) => `${Math.round(weight * 100)}% ${name}`)
    .join(" · ");

export const proposedAllocations = (persona: Persona): Record<StrategyKey, number> => {
  const { from, to, amount } = persona.scenario;
  return {
    ...persona.allocations,
    [from]: persona.allocations[from] - amount,
    [to]: persona.allocations[to] + amount,
  };
};
