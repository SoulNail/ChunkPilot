import { useEffect, useState } from "react";
import { api } from "../api";

export default function MCPInfo() {
  const [origin, setOrigin] = useState("");
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    setOrigin(window.location.origin);
    api.health().then(setHealth).catch(() => {});
  }, []);

  // 浏览器访问前端的地址即可推断后端对外地址（同机部署）。
  // 后端容器内监听 8000，compose 对外发布为 38000，故 MCP 对外地址用 38000。
  const base = origin.replace(/:\d+$/, ":38000");
  const mcpUrl = `${base}/mcp`;

  const claudeJson = `{
  "mcpServers": {
    "rag-qdrant": {
      "type": "http",
      "url": "${mcpUrl}"
    }
  }
}`;

  return (
    <div className="space-y-4">
      <div className="bg-white p-5 rounded-lg space-y-2">
        <h2 className="font-semibold text-slate-700">给第三方 Agent 接入的检索后端</h2>
        <p className="text-sm text-slate-500">
          本平台只负责「文档 + 切分/嵌入参数」的管理。真正的问答由 opencode / claude code /
          hermes 等 Agent 通过下面的 MCP 地址连接、调用检索工具来完成。
        </p>
        <div className="flex items-center gap-2">
          <code className="bg-slate-100 px-3 py-2 rounded text-sm flex-1 break-all">{mcpUrl}</code>
          <button
            onClick={() => navigator.clipboard.writeText(mcpUrl)}
            className="px-3 py-2 bg-indigo-600 text-white rounded-md text-sm whitespace-nowrap"
          >复制</button>
        </div>
        <p className="text-xs text-slate-400">
          传输方式：Streamable HTTP。对外地址为后端 38000 端口（容器内 8000，compose 映射到宿主 38000）。
        </p>
      </div>

      <div className="bg-white p-5 rounded-lg space-y-2">
        <h3 className="font-medium text-slate-700 text-sm">可用 MCP 工具</h3>
        <ul className="text-sm text-slate-600 list-disc pl-5 space-y-1">
          <li><code>list_knowledge_bases()</code> —— 列出所有知识库及用途（含建议回答风格）</li>
          <li><code>search_documents(query, collection, top_k=5, rerank=true)</code> —— 在指定库内混合检索+重排，返回相关片段</li>
        </ul>
      </div>

      <div className="bg-white p-5 rounded-lg space-y-2">
        <h3 className="font-medium text-slate-700 text-sm">Claude Code / 兼容客户端配置示例</h3>
        <pre className="bg-slate-900 text-slate-100 p-3 rounded text-xs overflow-x-auto">{claudeJson}</pre>
        <p className="text-xs text-slate-400">
          Claude Code 也可用命令：<code>claude mcp add --transport http rag-qdrant {mcpUrl}</code>
        </p>
      </div>

      <div className="text-xs text-slate-400">
        后端状态：{health ? (health.embedding_service?.status || health.embedding_service?.mode || "已连接")
          : "检测中…"} · 嵌入服务 {health?.embedding_service?.error ? "异常" : "正常"}
      </div>
    </div>
  );
}
