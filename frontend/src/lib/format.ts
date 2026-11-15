export function formatValue(value: number | null | undefined, unit: string, signed = false): string {
  if (value === null || value === undefined) return unit === "months" ? "not recovered" : "n/a";
  if (unit === "percent") return signed ? `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)} pts` : `${(value * 100).toFixed(1)}%`;
  if (unit === "months") return signed ? `${value >= 0 ? "+" : ""}${value.toFixed(0)} mo` : `${value.toFixed(0)} months`;
  if (unit === "cad") {
    const sign = value < 0 ? "-" : signed ? "+" : "";
    return `${sign}$${Math.abs(value).toLocaleString("en-CA", { maximumFractionDigits: 0 })}`;
  }
  return signed ? `${value >= 0 ? "+" : ""}${value.toFixed(3)}` : value.toFixed(3);
}

export const STRATEGY_LABELS: Record<string, string> = {
  growth: "Growth",
  dividend: "Dividend",
  momentum: "Momentum",
  preservation: "Capital preservation",
  esg: "ESG",
  quality: "Quality",
  balanced_index: "Balanced index",
  crypto: "Crypto",
};

export const STRATEGY_COLORS: Record<string, string> = {
  growth: "var(--coral)",
  dividend: "var(--blue)",
  momentum: "var(--gold)",
  preservation: "var(--sage)",
  esg: "#2f8f5b",
  quality: "#00314d",
  balanced_index: "#7fb2de",
  crypto: "#e6a100",
};

export function strategyLabel(name: string): string {
  if (name.startsWith("single_")) return name.slice("single_".length);
  return STRATEGY_LABELS[name] ?? name;
}

export function strategyColor(name: string): string {
  if (name.startsWith("single_")) return "#7b3fa0";
  return STRATEGY_COLORS[name] ?? "#94a3b8";
}
