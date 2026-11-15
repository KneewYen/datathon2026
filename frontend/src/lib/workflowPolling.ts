export type WorkflowPollSnapshot<T> = {
  status: string;
  result?: T | null;
  error?: string | null;
};

export type WorkflowPollOptions<T, Snapshot extends WorkflowPollSnapshot<T>> = {
  getStatus: () => Promise<Snapshot>;
  onStatus: (snapshot: Snapshot) => void;
  isRetryableError: (error: unknown) => boolean;
  sleep?: (milliseconds: number) => Promise<void>;
  intervalMs?: number;
  maxAttempts?: number;
  maxConsecutiveErrors?: number;
};

const wait = (milliseconds: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));

export async function pollWorkflow<T, Snapshot extends WorkflowPollSnapshot<T>>({
  getStatus,
  onStatus,
  isRetryableError,
  sleep = wait,
  intervalMs = 2_000,
  maxAttempts = 90,
  maxConsecutiveErrors = 4,
}: WorkflowPollOptions<T, Snapshot>): Promise<T> {
  let consecutiveErrors = 0;

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await sleep(intervalMs);
    let snapshot: Snapshot;
    try {
      snapshot = await getStatus();
      consecutiveErrors = 0;
    } catch (error) {
      consecutiveErrors += 1;
      if (!isRetryableError(error) || consecutiveErrors > maxConsecutiveErrors) {
        throw error;
      }
      continue;
    }

    onStatus(snapshot);
    if (snapshot.status === "SUCCEEDED") {
      if (snapshot.result) return snapshot.result;
      throw new Error("AWS workflow succeeded without an investment result");
    }
    if (snapshot.status !== "RUNNING") {
      throw new Error(snapshot.error ?? `AWS workflow ended with ${snapshot.status}`);
    }
  }

  throw new Error("AWS workflow status timed out in the browser");
}
