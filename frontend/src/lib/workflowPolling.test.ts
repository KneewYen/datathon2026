import assert from "node:assert/strict";
import test from "node:test";

import { pollWorkflow } from "./workflowPolling.ts";

const noWait = async () => {};

test("polls through transient failures and returns a successful result", async () => {
  const snapshots = [
    new TypeError("Failed to fetch"),
    { status: "RUNNING", result: null },
    { status: "SUCCEEDED", result: { answer: "grounded" } },
  ];
  const statuses: string[] = [];

  const result = await pollWorkflow({
    getStatus: async () => {
      const next = snapshots.shift();
      if (next instanceof Error) throw next;
      return next!;
    },
    onStatus: (snapshot) => statuses.push(snapshot.status),
    isRetryableError: (error) => error instanceof TypeError,
    sleep: noWait,
  });

  assert.deepEqual(result, { answer: "grounded" });
  assert.deepEqual(statuses, ["RUNNING", "SUCCEEDED"]);
});

test("does not retry non-transient authentication failures", async () => {
  let calls = 0;
  const unauthorized = Object.assign(new Error("Unauthorized"), { status: 401 });

  await assert.rejects(
    pollWorkflow({
      getStatus: async () => {
        calls += 1;
        throw unauthorized;
      },
      onStatus: () => {},
      isRetryableError: (error) => (error as { status?: number }).status === 429,
      sleep: noWait,
    }),
    /Unauthorized/,
  );
  assert.equal(calls, 1);
});

test("stops after the configured number of consecutive transient failures", async () => {
  let calls = 0;

  await assert.rejects(
    pollWorkflow({
      getStatus: async () => {
        calls += 1;
        throw new TypeError("Failed to fetch");
      },
      onStatus: () => {},
      isRetryableError: (error) => error instanceof TypeError,
      sleep: noWait,
      maxConsecutiveErrors: 2,
    }),
    /Failed to fetch/,
  );
  assert.equal(calls, 3);
});
