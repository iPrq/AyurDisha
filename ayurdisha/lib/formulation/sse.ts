export interface StepEvent {
  node: string;
  label: string;
  error?: string;
}

export interface StreamHandlers<T> {
  onStepStarted?: (e: StepEvent) => void;
  onStepCompleted?: (e: StepEvent) => void;
  onStepFailed?: (e: StepEvent) => void;
  onResult?: (result: T) => void;
}

export class StreamError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

/** Parses one SSE frame ("event: x\ndata: {...}") into its event name and JSON payload. */
export function parseSseFrame(frame: string): { event: string; data: unknown } | null {
  let event = "message";
  const data: string[] = [];
  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) };
  } catch {
    return null;
  }
}

/**
 * POSTs to a streaming endpoint and resolves with the final `result` payload.
 * Progress callbacks fire only for events the backend actually sent.
 */
export async function streamPost<T>(
  path: string,
  body: unknown,
  handlers: StreamHandlers<T> = {},
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(`/api/backend${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new StreamError(detail, res.status);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: T | undefined;
  let received = false;
  for (;;) {
    const { value, done } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.search(/\r?\n\r?\n/)) >= 0) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx).replace(/^\r?\n\r?\n/, "");
      const parsed = parseSseFrame(frame);
      if (!parsed) continue;
      const data = parsed.data as Record<string, unknown>;
      switch (parsed.event) {
        case "step_started":
          handlers.onStepStarted?.(data as unknown as StepEvent);
          break;
        case "step_completed":
          handlers.onStepCompleted?.(data as unknown as StepEvent);
          break;
        case "step_failed":
          handlers.onStepFailed?.(data as unknown as StepEvent);
          break;
        case "error":
          throw new StreamError(String(data.detail ?? "Run failed"), Number(data.status ?? 500));
        case "result":
          result = data as T;
          received = true;
          handlers.onResult?.(result);
          break;
      }
    }
    if (done) break;
  }
  if (!received) throw new StreamError("The run ended without a result.", 502);
  return result as T;
}
