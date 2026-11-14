"use client";
import { useState } from "react";
import type { Proposal } from "@/lib/api";
import { RISK_PROFILES } from "@/lib/profiles";

export function ProposalCard({
  proposal,
  disabled,
  onApprove,
  onReject,
}: {
  proposal: Proposal;
  disabled: boolean;
  onApprove: (risk: string) => void;
  onReject: () => void;
}) {
  const [risk, setRisk] = useState(proposal.risk);
  return (
    <div className="mt-3 space-y-3 rounded-lg border border-neutral-300 p-3 dark:border-neutral-700">
      <div className="text-sm">
        <b>{proposal.account_type}</b> · {proposal.horizon_label}
      </div>
      <fieldset disabled={disabled} className="space-y-1">
        <legend className="mb-1 text-xs text-neutral-500">Risk profile</legend>
        <div className="flex flex-wrap gap-2">
          {RISK_PROFILES.map((r) => (
            <label
              key={r.id}
              className={`cursor-pointer rounded-full border px-3 py-1 text-sm ${
                risk === r.id
                  ? "border-neutral-900 bg-neutral-900 text-white dark:border-white dark:bg-white dark:text-neutral-900"
                  : "border-neutral-300 dark:border-neutral-700"
              }`}
            >
              <input type="radio" name={`risk-${proposal.id}`} value={r.id} checked={risk === r.id} onChange={() => setRisk(r.id)} className="sr-only" />
              {r.label} <span className="opacity-60">· {r.persona}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex gap-2">
        <button
          disabled={disabled}
          onClick={() => onApprove(risk)}
          className="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm text-white disabled:opacity-40 dark:bg-white dark:text-neutral-900"
        >
          Approve & create
        </button>
        <button disabled={disabled} onClick={onReject} className="rounded-lg px-3 py-1.5 text-sm underline disabled:opacity-40">
          Decline
        </button>
      </div>
    </div>
  );
}
