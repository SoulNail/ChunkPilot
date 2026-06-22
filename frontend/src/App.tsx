import { useEffect, useState } from "react";
import { api } from "./api";
import Documents from "./pages/Documents";
import LLMConfig from "./pages/LLMConfig";
import Analyze from "./pages/Analyze";
import Search from "./pages/Search";
import MCPInfo from "./pages/MCPInfo";

const TABS = [
  { key: "docs", label: "文档管理", el: <Documents /> },
  { key: "llm", label: "LLM 配置（参数判定用）", el: <LLMConfig /> },
  { key: "analyze", label: "切分参数 / 灌库", el: <Analyze /> },
  { key: "search", label: "检索自测", el: <Search /> },
  { key: "mcp", label: "MCP 接入", el: <MCPInfo /> },
];

export default function App() {
  const [tab, setTab] = useState("docs");
  const [mode, setMode] = useState<string | null>(null);
  useEffect(() => { api.health().then((h) => setMode(h.embedding_mode)).catch(() => {}); }, []);
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-6">
        <h1 className="text-lg font-semibold text-indigo-600">RAG 文档 · 切分参数管理台</h1>
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-3 py-1.5 rounded-md text-sm transition ${
                tab === t.key
                  ? "bg-indigo-600 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
        {mode && (
          <span
            className="ml-auto text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-500"
            title={mode === "local" ? "嵌入/重排在后端进程内（不依赖 GPU 机）" : "嵌入/重排调用远程 GPU 服务"}
          >
            嵌入：{mode === "local" ? "本地" : "GPU 机"}
          </span>
        )}
      </header>
      <main className="max-w-5xl mx-auto p-6">
        {TABS.find((t) => t.key === tab)?.el}
      </main>
    </div>
  );
}
