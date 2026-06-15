// 后端 API 封装

async function req<T>(url: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(url, opts);
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw new Error(detail.detail || `请求失败 ${r.status}`);
  }
  return r.json();
}

export interface ChunkParams {
  chunk_size: number;
  chunk_overlap: number;
  separators: string[] | null;
  prepend_heading_path: boolean;
}

export interface Doc {
  name: string;
  size_bytes: number;
  collection: string;
  params?: ChunkParams | null;
  analysis?: Record<string, any> | null;
  status?: "new" | "ingesting" | "done" | "error";
  points_count?: number | null;
  error?: string | null;
  updated_at?: string | null;
}

export const api = {
  // 文档
  listDocs: () => req<Doc[]>("/api/docs"),
  uploadDoc: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return req<Doc>("/api/docs", { method: "POST", body: fd });
  },
  deleteDoc: (name: string) =>
    req(`/api/docs/${encodeURIComponent(name)}`, { method: "DELETE" }),
  downloadUrl: (name: string) => `/api/docs/${encodeURIComponent(name)}`,

  // LLM
  getLLM: () => req<any>("/api/llm/config"),
  setLLM: (cfg: { base_url: string; api_key: string; model: string }) =>
    req<any>("/api/llm/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg),
    }),
  testLLM: () => req<any>("/api/llm/test", { method: "POST" }),

  // 切分分析
  analyze: (filename: string) =>
    req<any>("/api/chunking/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    }),
  // 手动保存某文档的切分参数（不经 LLM）
  saveParams: (filename: string, params: ChunkParams, collection?: string, answer_prompt?: string) =>
    req<any>(`/api/chunking/params/${encodeURIComponent(filename)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ params, collection, answer_prompt }),
    }),

  // 健康/接入信息
  health: () => req<any>("/api/health"),

  // 灌库
  startIngest: (body: any) =>
    req<{ job_id: string; collection: string }>("/api/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  // 检索
  collections: () => req<string[]>("/api/search/collections"),
  search: (body: any) =>
    req<any[]>("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};

// SSE：灌库进度（轮询型 SSE，直接用 EventSource）
export function ingestStream(jobId: string, onMsg: (j: any) => void, onEnd: () => void) {
  const es = new EventSource(`/api/ingest/${jobId}/stream`);
  es.onmessage = (e) => {
    const j = JSON.parse(e.data);
    onMsg(j);
    if (j.status === "done" || j.status === "error") {
      es.close();
      onEnd();
    }
  };
  es.onerror = () => { es.close(); onEnd(); };
  return es;
}
