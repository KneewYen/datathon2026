import type { ChatResponse } from "@/lib/api";
import { ProposalCard } from "./ProposalCard";

export type ChatMessage =
  | { role: "user"; text: string }
  | { role: "assistant"; data: ChatResponse; resolved?: boolean };

function Markdownish({ text }: { text: string }) {
  return (
    <div className="space-y-2 whitespace-pre-wrap">
      {text.split("\n\n").map((block, i) => (
        <p key={i}>
          {block.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
            part.startsWith("**") ? <b key={j}>{part.slice(2, -2)}</b> : part
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
      <div className="ml-auto max-w-[80%] rounded-2xl bg-neutral-900 px-4 py-2 text-white dark:bg-white dark:text-neutral-900">
        {msg.text}
      </div>
    );
  }
  const d = msg.data;
  const metrics = Object.entries(d.metrics ?? {});
  return (
    <div className="max-w-[90%] rounded-2xl border border-neutral-200 px-4 py-3 dark:border-neutral-800">
      <Markdownish text={d.answer} />

      {metrics.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {metrics.map(([k, v]) => (
            <div key={k} className="rounded-md bg-neutral-100 p-2 dark:bg-neutral-900">
              <div className="text-xs text-neutral-500">{k}</div>
              <div className="font-mono text-sm">{v}</div>
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
            <button key={s} onClick={() => onSuggestion(s)} className="rounded-full border border-neutral-300 px-3 py-1 text-sm dark:border-neutral-700">
              {s}
            </button>
          ))}
        </div>
      )}

      {(d.trace?.length > 0 || d.sources?.length > 0) && (
        <details className="mt-3 text-xs text-neutral-500">
          <summary className="cursor-pointer">How I got this</summary>
          <ol className="mt-2 space-y-1">
            {d.trace.map((t, i) => (
              <li key={i}>
                {i + 1}. <b>{t.agent}</b>: {t.action}
              </li>
            ))}
          </ol>
          {d.sources?.length > 0 && (
            <ul className="mt-2 list-disc pl-4">
              {d.sources.map((s) => <li key={s}>{s}</li>)}
            </ul>
          )}
        </details>
      )}

      {d.warnings?.length > 0 && <p className="mt-2 text-xs text-amber-600">{d.warnings.join(" ")}</p>}
    </div>
  );
}
