"use client";

import { useState } from "react";
import type { AnswerSegment, EvidenceEntry } from "@/lib/api";

function shortSource(source: string) {
  return source
    .split("; ")
    .map((item) => item.replace(/^s3:\/\/[^/]+\//, "s3://…/"))
    .join(" · ");
}

/** Renders an explanation where every number is a button that reveals its provenance. */
export function EvidenceAnswer({
  segments,
  evidence,
  fallback,
  tone = "dark",
}: {
  segments: AnswerSegment[];
  evidence: Record<string, EvidenceEntry>;
  fallback: string;
  tone?: "dark" | "light";
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const entry = selected ? evidence[selected] : null;
  const chip =
    tone === "dark"
      ? "bg-white/15 text-white ring-white/40 hover:bg-white/25"
      : "bg-brand-50 text-brand-800 ring-brand-200 hover:bg-brand-100";

  if (!segments.length) return <p className="whitespace-pre-wrap text-sm leading-relaxed">{fallback}</p>;

  return (
    <div>
      <p className="whitespace-pre-wrap text-sm leading-relaxed">
        {segments.map((segment, index) =>
          segment.type === "text" ? (
            <span key={index}>{segment.text}</span>
          ) : (
            <button
              key={index}
              type="button"
              onClick={() => setSelected(selected === segment.token ? null : segment.token)}
              aria-pressed={selected === segment.token}
              title="Show where this number comes from"
              className={`mx-0.5 rounded px-1.5 py-0.5 font-mono text-[13px] font-semibold ring-1 transition ${chip}`}
            >
              {segment.text}
            </button>
          ),
        )}
      </p>
      <p className={`mt-2 text-[11px] ${tone === "dark" ? "text-white/60" : "text-slate-500"}`}>
        Every number above was inserted by code from AWS Lambda evidence, not written by the model. Click one to verify it.
      </p>
      {entry && (
        <dl
          className={`mt-3 grid gap-x-4 gap-y-1 rounded-md p-3 text-xs sm:grid-cols-[140px_1fr] ${
            tone === "dark" ? "bg-black/25 text-white/90" : "bg-slate-50 text-slate-700 ring-1 ring-slate-200"
          }`}
        >
          <dt className="font-semibold">Figure</dt>
          <dd>
            {entry.label} · {entry.role}: <b>{entry.display}</b>
          </dd>
          <dt className="font-semibold">Evidence ID</dt>
          <dd className="font-mono">{entry.evidence_id}</dd>
          <dt className="font-semibold">Raw value</dt>
          <dd className="font-mono">{entry.value === null ? "null" : entry.value}</dd>
          <dt className="font-semibold">Formula</dt>
          <dd className="font-mono">{entry.formula_version}</dd>
          <dt className="font-semibold">Source</dt>
          <dd className="break-all font-mono">{shortSource(entry.source)}</dd>
        </dl>
      )}
    </div>
  );
}
