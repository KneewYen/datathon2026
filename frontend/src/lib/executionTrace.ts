import type { ExecutionEvent } from "./api";

export type ExecutionTraceRow = {
  event: ExecutionEvent;
  depth: number;
};

export function traceRows(events: ExecutionEvent[]): ExecutionTraceRow[] {
  const byId = new Map(events.map((event) => [event.event_id, event]));
  return events.map((event) => {
    let depth = 0;
    let parent = event.parent_id;
    const visited = new Set<string>();
    while (parent && byId.has(parent) && !visited.has(parent)) {
      visited.add(parent);
      depth += 1;
      parent = byId.get(parent)?.parent_id ?? null;
    }
    return { event, depth };
  });
}
