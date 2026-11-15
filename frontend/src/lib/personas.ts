export type PersonaId = "amira" | "mateo" | "robert";

export type Persona = {
  id: PersonaId;
  name: string;
  age: number;
  horizon: string;
  risk: string;
  goal: string;
  tests: string;
  strategies: string[];
};

export const PERSONAS: Persona[] = [
  {
    id: "amira",
    name: "Amira",
    age: 26,
    horizon: "15+ years",
    risk: "High",
    goal: "Long-term growth, still diversified",
    tests: "High risk does not mean anything goes",
    strategies: ["Growth", "Momentum", "Crypto (capped)", "Balanced index"],
  },
  {
    id: "mateo",
    name: "Mateo",
    age: 41,
    horizon: "8–12 years",
    risk: "Moderate",
    goal: "Balanced growth with ESG",
    tests: "Values, not just return and risk",
    strategies: ["Balanced index", "ESG", "Dividend", "Growth"],
  },
  {
    id: "robert",
    name: "Robert",
    age: 59,
    horizon: "3–5 years",
    risk: "Low–moderate",
    goal: "Preserve capital, some growth",
    tests: "Pushing back on a tempting request",
    strategies: ["Capital preservation", "Quality", "Dividend"],
  },
];