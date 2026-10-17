export type DocStatus = "queued" | "processing" | "ready" | "failed";

export interface Doc {
  id: string;
  filename: string;
  title: string | null;
  size_bytes: number;
  status: DocStatus;
  progress: string | null;
  error: string | null;
  page_count: number;
  ocr_pages: number;
  chunk_count: number;
  created_at: string;
  ready_at: string | null;
}

export interface Citation {
  n: number;
  document_id: string;
  filename: string;
  title: string | null;
  page: number;
  snippet: string;
  boxes: [number, number, number, number][];
  score: number | null;
}

export interface Passage {
  document_id: string;
  filename: string;
  page: number;
  similarity: number;
  rerank_score: number | null;
  text: string;
}

export interface AskResponse {
  question: string;
  answer: string;
  answerable: boolean;
  citations: Citation[];
  passages: Passage[];
  mode: "llm" | "extractive";
  timings_ms: Record<string, number>;
  refusal_reason: string | null;
}

export interface Health {
  status: string;
  llm_provider: string;
  model: string | null;
  embed_model: string;
  rerank: boolean;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail
        : body.detail?.message ?? JSON.stringify(body.detail ?? body);
    } catch {
      /* keep status text */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/api/health"),
  documents: () => request<Doc[]>("/api/documents"),

  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Doc>("/api/documents", { method: "POST", body: form });
  },

  remove: (id: string) => request<void>(`/api/documents/${id}`, { method: "DELETE" }),
  reindex: (id: string) => request<{ id: string }>(`/api/documents/${id}/reindex`, { method: "POST" }),

  ask: (question: string, documentIds: string[]) =>
    request<AskResponse>("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, document_ids: documentIds.length ? documentIds : null }),
    }),

  pageImage: (docId: string, page: number, width = 900) =>
    `${BASE}/api/documents/${docId}/pages/${page}/image?width=${width}`,
};

export const isPending = (d: Doc) => d.status === "queued" || d.status === "processing";
