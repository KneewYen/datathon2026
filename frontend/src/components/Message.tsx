import type { ChatResponse } from "@/lib/api";
import { ProposalCard } from "./ProposalCard";

export type ChatMessage =
  | { role: "user"; text: string }
  | { role: "assistant"; data: ChatResponse; resolved?: boolean };

function Rich({ text }: { text: string }) {
  return (
    <div className="space-y-2 whitespace-pre-wrap leading-relaxed">
      {text.split("\n\n").map((block, i) => (
        <p key={i}>
          {block.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
            part.startsWith("**") ? (
              <b key={j} className="font-semibold text-brand-700">
                {part.slice(2, -2)}
              </b>
            ) : (
              part
            )
          )}
        </p>
      ))}
    </div>
  );
}

export function Message({
  msg,
  busy,
  onSuggestion,
  onApprove,
  onReject,
}: {
  msg: ChatMessage;
  busy: boolean;
  onSuggestion: (s: string) => void;
  onApprove: (id: string, risk: string) => void;
  onReject: (id: string) => void;
}) {
  if (msg.role === "user") {
    return (
      <div className="ml-auto max-w-[80%] rounded-lg rounded-br-md bg-brand-500 px-4 py-2 text-white">{msg.text}</div>
    );
  }
  const d = msg.data;
  const metrics = Object.entries(d.metrics ?? {});
  return (
    <div className="flex gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
        AI
      </div>
      <div className="min-w-0 max-w-[90%] flex-1 rounded-lg rounded-tl-md bg-white px-4 py-3 ring-1 ring-slate-200">
        <Rich text={d.answer} />

        {metrics.length > 0 && (
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {metrics.map(([k, v]) => (
              <div key={k} className="rounded-lg bg-brand-50 p-2">
                <div className="text-xs text-slate-500">{k}</div>
                <div className="font-mono text-sm font-semibold text-brand-800">{v}</div>
              </div>
            ))}
          </div>
        )}

        {d.proposal && !msg.resolved && (
          <ProposalCard
            proposal={d.proposal}
            disabled={busy}
            onApprove={(risk) => onApprove(d.proposal!.id, risk)}
            onReject={() => onReject(d.proposal!.id)}
          />
        )}

        {d.suggestions?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {d.suggestions.map((s) => (
              <button
                key={s}
                onClick={() => onSuggestion(s)}
                disabled={busy}
                className="rounded-full bg-white px-3 py-1 text-sm text-link ring-1 ring-slate-300 transition hover:bg-slate-50 disabled:opacity-40"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {d.trace?.length > 0 && (
          <details className="mt-3 text-xs text-slate-500">
            <summary className="cursor-pointer text-brand-600 hover:text-brand-700">How I got this</summary>
            <ol className="mt-2 space-y-1">
              {d.trace.map((t, i) => (
                <li key={i}>
                  {i + 1}. <b className="text-slate-700">{t.agent}</b>: {t.action}
                </li>
              ))}
            </ol>
            {d.sources?.length > 0 && (
              <ul className="mt-2 list-disc pl-4">
                {d.sources.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            )}
          </details>
        )}

        {d.warnings?.length > 0 && <p className="mt-2 text-xs text-slate-400">{d.warnings.join(" ")}</p>}
      </div>
    </div>
  );
}
