import assert from "node:assert/strict";
import test from "node:test";

import type { ExecutionEvent } from "./api";
import { traceRows } from "./executionTrace.ts";

function event(
  event_id: string,
  parent_id: string | null,
  kind: ExecutionEvent["kind"],
  tool_name: string | null = null,
): ExecutionEvent {
  return {
    event_id,
    parent_id,
    request_id: "request-test",
    kind,
    agent: event_id,
    tool_name,
    started_at: "2026-11-15T12:00:00Z",
    ended_at: "2026-11-15T12:00:01Z",
    status: "completed",
    evidence_ids: tool_name ? ["evidence.test"] : [],
    input_summary: "input",
    output_summary: "output",
    error: null,
  };
}

test("trace rows preserve the actual orchestrator, account, strategy, and tool hierarchy", () => {
  const rows = traceRows([
    event("orchestrator", null, "orchestrator"),
    event("account.tfsa", "orchestrator", "agent"),
    event("strategy.growth", "account.tfsa", "agent"),
    event("tool.exposure", "strategy.growth", "tool", "analyze_holdings_exposure"),
  ]);

  assert.deepEqual(rows.map((row) => row.depth), [0, 1, 2, 3]);
  assert.equal(rows[3].event.tool_name, "analyze_holdings_exposure");
  assert.deepEqual(rows[3].event.evidence_ids, ["evidence.test"]);
});

test("trace rows stop safely when malformed events contain a parent cycle", () => {
  const rows = traceRows([
    event("one", "two", "agent"),
    event("two", "one", "agent"),
  ]);

  assert.deepEqual(rows.map((row) => row.depth), [2, 2]);
});
