import type {
  NbaAbsRequest,
  NbaAbsResponse,
  PatentAdvisorRequest,
  PatentAdvisorResponse,
  ProductReviewRequest,
  ProductReviewResponse,
} from "./types";

const BASE = "/api/backend";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) throw new Error(formatError(res.status, data));
  return data as T;
}

function formatError(status: number, data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d: { loc?: unknown[]; msg?: string }) =>
          `${(d.loc ?? []).slice(1).join(".")}: ${d.msg ?? ""}`,
        )
        .join("; ");
    }
  }
  if (typeof data === "string" && data) return `${status}: ${data}`;
  return `Request failed with status ${status}`;
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => request<{ status: string }>("/health"),
  productReview: (body: ProductReviewRequest) =>
    post<ProductReviewResponse>("/api/v1/product-review", body),
  patentAdvisor: (body: PatentAdvisorRequest) =>
    post<PatentAdvisorResponse>("/api/v1/patent-advisor", body),
  nbaAbs: (body: NbaAbsRequest) =>
    post<NbaAbsResponse>("/api/v1/nba-abs", body),
};
