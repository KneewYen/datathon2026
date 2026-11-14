import { useRef, useState } from "react";
import type { Account, AnalysisResponse } from "@/lib/api";
import { PERSONAS, formatCad, type PersonaId } from "@/lib/personas";
import { RISK_LEVEL } from "@/lib/profiles";
import { RiskMeter } from "./RiskMeter";

const HORIZON: Record<string, string> = {
  short: "3–5 yrs",
  mid: "8–12 yrs",
  long: "15+ yrs",
};

function Flag() {
  return (
    <svg
      viewBox="0 0 16 16"
      className="h-4 w-4 shrink-0 text-brand-500"
      fill="currentColor"
      aria-hidden
    >
      <path d="M2 1h1.5v14H2zM4 2h9l-2 3.2L13 8.5H4z" />
    </svg>
  );
}

const REVEAL = 80; // px of swipe that exposes the ✕

function SwipeRow({
  children,
  onRemove,
}: {
  children: React.ReactNode;
  onRemove: () => void;
}) {
  const [dx, setDx] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [removing, setRemoving] = useState(false);
  const rowRef = useRef<HTMLDivElement>(null);
  const start = useRef<{ x: number; base: number } | null>(null);
  const moved = useRef(false);

  const end = () => {
    if (!start.current) return;
    start.current = null;
    setDragging(false);
    const width = rowRef.current?.offsetWidth ?? 0;
    if (width > 0 && -dx >= width / 2) {
      // slide the row out, collapse its height, then drop it from the list
      setDx(-width);
      setRemoving(true);
      window.setTimeout(onRemove, 300);
    } else setDx(-dx >= REVEAL / 2 ? -REVEAL : 0);
  };

  return (
    <div
      ref={rowRef}
      className="relative overflow-hidden transition-[max-height,opacity] duration-300"
      style={removing ? { maxHeight: 0, opacity: 0 } : { maxHeight: 200 }}
    >
      <button
        type="button"
        onClick={onRemove}
        aria-label="Remove account"
        tabIndex={dx === 0 ? -1 : 0}
        className="absolute inset-y-0 right-0 flex items-center justify-end bg-red-600 pr-6 text-lg font-semibold text-white"
        style={{ width: Math.max(-dx, 0) }}
      >
        ✕
      </button>
      <div
        className="relative bg-white"
        style={{
          transform: `translateX(${dx}px)`,
          transition: dragging ? "none" : "transform 180ms ease",
          touchAction: "pan-y",
        }}
        onPointerDown={(e) => {
          start.current = { x: e.clientX, base: dx };
          moved.current = false;
        }}
        onPointerMove={(e) => {
          if (!start.current) return;
          const delta = e.clientX - start.current.x;
          if (!dragging && Math.abs(delta) > 6) {
            setDragging(true);
            e.currentTarget.setPointerCapture(e.pointerId);
          }
          if (Math.abs(delta) > 6) moved.current = true;
          setDx(Math.min(0, start.current.base + delta));
        }}
        onPointerUp={end}
        onPointerCancel={end}
        onClickCapture={(e) => {
          if (moved.current) {
            e.stopPropagation();
            e.preventDefault();
            moved.current = false;
          }
        }}
      >
        {children}
      </div>
    </div>
  );
}

export function AccountsPanel({
  personaId,
  analysis,
  accounts,
  selectedId,
  onSelect,
  onNew,
  onDelete,
}: {
  personaId: PersonaId;
  analysis: AnalysisResponse | null;
  accounts: Account[];
  selectedId: string | null;
  onSelect: (a: Account) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}) {
  const persona = PERSONAS.find((p) => p.id === personaId)!;
  const balance = persona.startingBalance;
  const invested = accounts.reduce((sum, a) => sum + (a.balance ?? 0), 0);
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 sm:p-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold">My accounts</h2>
          <p className="text-xs text-slate-500">
            Click an account to ask about it
          </p>
        </div>
        <button
          onClick={onNew}
          aria-label="Create account"
          title="Create account"
          className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-500 text-2xl leading-none text-white transition hover:bg-brand-600"
        >
          +
        </button>
      </div>

      <div className="mt-4 rounded-md bg-slate-50 px-4 py-3 ring-1 ring-slate-200">
        <div className="text-xs uppercase tracking-wide text-slate-500">
          Total balance
        </div>
        <div className="text-2xl font-semibold">
          {formatCad(balance + invested)}
        </div>
      </div>

      {analysis && (
        <div className="mt-5 rounded-md bg-slate-50 px-4 py-3 ring-1 ring-slate-200">
          <div className="text-xs uppercase tracking-wide text-slate-500">
            AWS Live Scenario
          </div>
          <ul className="mt-2 space-y-1 text-xs">
            {Object.entries(analysis.proposed_allocations).map(
              ([name, weight]) => (
                <li key={name} className="flex justify-between text-slate-600">
                  <span className="capitalize">{name}</span>
                  <span className="font-medium text-slate-800">
                    {formatCad(balance * weight)}
                  </span>
                </li>
              ),
            )}
          </ul>
        </div>
      )}

      <h3 className="mt-5 border-b border-slate-200 pb-2 text-sm font-semibold">
        My simulated accounts
      </h3>
      {accounts.length === 0 && (
        <p className="py-4 text-sm text-slate-500">
          No accounts yet. Use + to open one.
        </p>
      )}
      <ul>
        {accounts.map((a) => (
          <li key={a.id} className="border-b border-slate-200">
            <SwipeRow onRemove={() => onDelete(a.id)}>
              <button
                onClick={() => onSelect(a)}
                className={`flex w-full items-center gap-3 px-2 py-4 text-left transition hover:bg-slate-50 ${
                  a.id === selectedId
                    ? "bg-slate-50 shadow-[inset_3px_0_0_#e41c23]"
                    : ""
                }`}
              >
                <Flag />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">{a.name}</span>
                  <span className="block truncate text-xs text-slate-500">
                    {a.horizon_agent} · {HORIZON[a.horizon]} ·{" "}
                    {a.strategies.join(", ")}
                  </span>
                </span>
                <span className="w-28 shrink-0">
                  <span className="block text-right text-sm font-semibold">
                    {formatCad(a.balance ?? 0)}
                  </span>
                  <span className="mb-1 block text-right text-xs text-slate-500">
                    {a.risk_label}
                  </span>
                  <RiskMeter level={RISK_LEVEL[a.risk] ?? 0} />
                </span>
              </button>
            </SwipeRow>
          </li>
        ))}
      </ul>
      <button
        onClick={onNew}
        className="mt-3 text-sm font-medium text-link hover:underline"
      >
        + Open an account
      </button>
      <p className="mt-3 text-[11px] text-slate-400">
        Fictional accounts are stored in memory for this demo session only.
      </p>
    </section>
  );
}
