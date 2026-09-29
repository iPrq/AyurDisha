import type { AgentAction, PlannedAction } from "@/lib/agent/actions";
import type {
  NbaAbsRequest,
  NbaAbsResponse,
  PatentAdvisorRequest,
  PatentAdvisorResponse,
  ProductReviewRequest,
  ProductReviewResponse,
} from "@/lib/types";
import { streamPost, type StreamHandlers } from "./sse";
import type {
  AnalyzeResponse,
  ClarificationRequest,
  CreateFormulationRequest,
  FormulationContext,
  FormulationEnvelope,
  LanguageCapabilities,
  ReadinessResponse,
  ScenarioChange,
  ScenarioResult,
  SpeakResult,
  ToolHandoff,
  ToolName,
  TranscribeResponse,
  TranslateResult,
  VersionComparison,
} from "./types";

const BASE = "/api/backend/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData;
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: isForm ? init?.headers : { "Content-Type": "application/json", ...init?.headers },
  });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    if (data && typeof data === "object" && "detail" in data) {
      const d = (data as { detail: unknown }).detail;
      if (typeof d === "string") detail = d;
      else if (Array.isArray(d)) detail = d.map((x: { msg?: string }) => x.msg ?? "").join("; ");
    }
    throw new ApiError(detail, res.status);
  }
  return data as T;
}

const post = <T>(path: string, body?: unknown) =>
  call<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export interface ActionResult {
  ok: boolean;
  action_type: string;
  summary: string;
  context: FormulationContext;
  changed_ingredient_id: string | null;
  changed_fields: string[];
}

export interface AgentPlanResponse {
  run_id: string;
  intent: string;
  intents: string[];
  message: string;
  actions: PlannedAction[];
  clarification: ClarificationRequest | null;
  requires_confirmation: boolean;
  original_text: string;
  normalized_text: string;
  language: string | null;
  language_method: string | null;
  translation_note: string | null;
  message_localized: string | null;
  decoder: "llm" | "rules" | "command";
}

export interface ChatRequest {
  message: string;
  formulation_id?: string | null;
  original_text?: string | null;
  language?: string | null;
  source?: "text" | "voice";
  current_route?: string | null;
}

export const formulationApi = {
  create: (body: CreateFormulationRequest) => post<FormulationEnvelope>("/formulation", body),
  upload: (file: File, kind: "formulation" | "patent") => {
    const form = new FormData();
    form.append("file", file);
    form.append("kind", kind);
    return call<FormulationEnvelope>("/formulation/upload", { method: "POST", body: form });
  },
  get: (id: string) => call<FormulationEnvelope>(`/formulation/${encodeURIComponent(id)}`),
  action: (id: string, action: AgentAction, baseVersion?: number) =>
    post<ActionResult>(`/formulation/${encodeURIComponent(id)}/actions`, {
      action,
      base_version: baseVersion ?? null,
    }),
  confirm: (id: string) => post<ActionResult>(`/formulation/${encodeURIComponent(id)}/confirm`),
  analyze: (id: string) => post<AnalyzeResponse>(`/formulation/${encodeURIComponent(id)}/analyze`),
  analyzeStream: (id: string, handlers: StreamHandlers<AnalyzeResponse>, signal?: AbortSignal) =>
    streamPost<AnalyzeResponse>(
      `/api/v1/formulation/${encodeURIComponent(id)}/analyze/stream`,
      undefined,
      handlers,
      signal,
    ),
  readiness: (id: string, tool: ToolName) =>
    post<ReadinessResponse>(`/formulation/${encodeURIComponent(id)}/readiness`, { tool }),
  handoff: (id: string, tool: ToolName) =>
    call<ToolHandoff>(`/formulation/${encodeURIComponent(id)}/handoff/${tool}`),
  scenario: (id: string, changes: ScenarioChange[]) =>
    post<ScenarioResult>(`/formulation/${encodeURIComponent(id)}/scenario`, { changes }),
  compare: (id: string, from?: number | null, to?: number | null) => {
    const q = new URLSearchParams();
    if (from != null) q.set("from_version", String(from));
    if (to != null) q.set("to_version", String(to));
    return call<VersionComparison>(`/formulation/${encodeURIComponent(id)}/compare?${q}`);
  },
  chat: (body: ChatRequest) => post<AgentPlanResponse>("/formulation/chat", body),
};

export const toolStreams = {
  review: (body: ProductReviewRequest & { formulation_id?: string | null }, h: StreamHandlers<ProductReviewResponse>) =>
    streamPost<ProductReviewResponse>("/api/v1/product-review/stream", body, h),
  patent: (body: PatentAdvisorRequest & { formulation_id?: string | null }, h: StreamHandlers<PatentAdvisorResponse>) =>
    streamPost<PatentAdvisorResponse>("/api/v1/patent-advisor/stream", body, h),
  nbaAbs: (body: NbaAbsRequest & { formulation_id?: string | null }, h: StreamHandlers<NbaAbsResponse>) =>
    streamPost<NbaAbsResponse>("/api/v1/nba-abs/stream", body, h),
};

export const languageApi = {
  capabilities: () => call<LanguageCapabilities>("/language/capabilities"),
  transcribe: (audio: Blob, language: string) => {
    const form = new FormData();
    form.append("file", new File([audio], "speech.wav", { type: "audio/wav" }));
    form.append("language", language);
    return call<TranscribeResponse>("/language/transcribe", { method: "POST", body: form });
  },
  translate: (text: string, source: string, target: string) =>
    post<TranslateResult>("/language/translate", {
      text,
      source_language: source,
      target_language: target,
    }),
  speak: (text: string, language: string) => post<SpeakResult>("/language/speak", { text, language }),
};
