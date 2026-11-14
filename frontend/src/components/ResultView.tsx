import type { ChatResponse } from "@/lib/api";

export function ResultView({
  question,
  result,
  onNew,
}: {
  question: string;
  result: ChatResponse;
  onNew: () => void;
}) {
  const metrics = Object.entries(result.metrics ?? {});
  return (
    <div className="space-y-6">
      <div className="text-sm text-neutral-500">“{question}”</div>

      <section>
        <h2 className="mb-2 font-semibold">Answer</h2>
        <p>{result.answer}</p>
      </section>

      {metrics.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">Metrics</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {metrics.map(([k, v]) => (
              <div key={k} className="rounded-lg border border-neutral-200 p-3 dark:border-neutral-800">
                <div className="text-xs text-neutral-500">{k}</div>
                <div className="font-mono">{String(v)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {result.warnings?.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">Warnings</h2>
          <ul className="list-disc pl-5 text-sm text-amber-600">
            {result.warnings.map((w) => <li key={w}>{w}</li>)}
          </ul>
        </section>
      )}

      <details className="rounded-lg border border-neutral-200 p-3 dark:border-neutral-800" open>
        <summary className="cursor-pointer font-semibold">Agent trace</summary>
        <ol className="mt-3 space-y-2 text-sm">
          {result.trace.map((t, i) => {
            const { step, ...rest } = t;
            return (
              <li key={i} className="flex gap-3">
                <span className="font-mono text-neutral-400">{i + 1}</span>
                <span className="font-medium">{step}</span>
                <span className="text-neutral-500">
                  {Object.entries(rest).map(([k, v]) => `${k}: ${String(v)}`).join(" · ")}
                </span>
              </li>
            );
          })}
        </ol>
      </details>

      <button onClick={onNew} className="text-sm underline">Ask another question</button>
    </div>
  );
}
