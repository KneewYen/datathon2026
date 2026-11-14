import { PERSONAS, type Persona } from "@/lib/personas";

export function PersonaPicker({ onPick }: { onPick: (p: Persona) => void }) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {PERSONAS.map((p) => (
        <button
          key={p.id}
          onClick={() => onPick(p)}
          className="rounded-xl border border-neutral-200 p-5 text-left transition hover:border-neutral-900 dark:border-neutral-800 dark:hover:border-white"
        >
          <div className="text-lg font-semibold">
            {p.name} <span className="font-normal text-neutral-500">· {p.age}</span>
          </div>
          <div className="mt-1 text-sm text-neutral-500">{p.goal}</div>
          <dl className="mt-4 space-y-1 text-sm">
            <div><dt className="inline text-neutral-500">Horizon: </dt><dd className="inline">{p.horizon}</dd></div>
            <div><dt className="inline text-neutral-500">Risk: </dt><dd className="inline">{p.risk}</dd></div>
            <div><dt className="inline text-neutral-500">Agent: </dt><dd className="inline">{p.horizonAgent}</dd></div>
          </dl>
        </button>
      ))}
    </div>
  );
}
