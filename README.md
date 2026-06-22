# ChunkPilot

> A RAG knowledge-base console: LLM-assisted chunking, vector ingestion, and an
> MCP server that serves retrieval to your agents.

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.12+-3776ab)

一个 **RAG 知识库管理后台**，不是问答产品。它负责：管理文档、为每个
文档设定切分/嵌入参数、灌进 Qdrant；真正的问答由外部 Agent（opencode / claude code /
hermes 等）通过 **MCP** 连到本服务、调用检索工具自行完成。

- 前端：管理文档 + 每文档切分参数（手动填写）+ 灌库 + 调试检索。
- 切分参数：前端手动填写，或后续由外部 Agent（hermes）经接口提供。
- 对外检索：后端 `/mcp` 暴露 MCP 工具（混合检索 + 重排）给第三方 Agent。

## 架构

```
192.168.110.51 (N100)                      192.168.110.3 (RTX 3060Ti)
┌───────────────────────────┐             ┌──────────────────────────┐
│ frontend (React/nginx :80)│             │ embedding_service :8001  │
│ backend  (FastAPI :8000)  │──HTTP──────▶│  /embed  BGE-M3 稠密+稀疏 │
│   ├─ /api  管理用 REST     │             │  /rerank bge-reranker    │
│   └─ /mcp  Agent 检索入口  │◀── MCP ──── opencode / claude code / hermes
│ qdrant   (:6333)          │             └──────────────────────────┘
└───────────────────────────┘
        └─ 切分参数：前端手动填写，或由外部 Agent(hermes) 经接口提供
```

## MCP 接入（给 Agent 用）

部署后 Agent 连接 `http://<部署IP>:38000/mcp`（Streamable HTTP）。
后端容器内部仍监听 8000，compose 把它映射到宿主 **38000** 对外（见 `docker-compose.app.yml`）。暴露工具：

| 工具 | 作用 |
|------|------|
| `list_knowledge_bases()` | 列出所有知识库、向量数、来源文档、建议回答风格 |
| `search_documents(query, collection, top_k=5, rerank=True)` | 指定库内混合检索+重排，返回相关片段 |

```bash
# Claude Code 接入示例
claude mcp add --transport http rag-qdrant http://192.168.110.51:38000/mcp
```

## 目录

| 路径 | 说明 | 部署位置 |
|------|------|---------|
| `embedding_service/` | GPU 推理服务（嵌入+重排） | 110.3 |
| `backend/` | 主应用后端（文档/LLM/切分/灌库/检索 + MCP） | 110.51 |
| `frontend/` | React 前端（文档/切分参数/检索/MCP 接入） | 110.51 |
| `ingest.py` / `search.py` | 原始 CLI 工具（直连 GPU 本地嵌入） | — |

## 本地开发

```bash
# 1) GPU 推理服务（本机 3060Ti）
cd embedding_service && uv run uvicorn app:app --host 0.0.0.0 --port 8001

# 2) 后端
cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
#    默认 EMBEDDING_SERVICE_URL=http://localhost:8001, QDRANT_URL=http://192.168.110.51:6333

# 3) 前端（dev，自动反代 /api → :8000）
cd frontend && npm install && npm run dev
```

打开前端 → 「文档管理」上传 → 「切分参数 / 灌库」手动填参数并灌库 →「检索（调试）」自测召回 →「MCP 接入」把地址给 Agent。

## Docker 部署

```bash
# 在 110.3（GPU 机）：
docker compose -f docker-compose.gpu.yml up -d --build

# 在 110.51（N100）：
docker compose -f docker-compose.app.yml up -d --build
```

> 若 110.51 上已单独运行 Qdrant，可删除 `docker-compose.app.yml` 里的 `qdrant` 服务，并把 `RAG_QDRANT_URL` 改成现有地址。

### 单机自包含部署（不依赖 GPU 机）

想让一台机器（如 N100）独立跑、不连任何 GPU 机：

```bash
docker compose -f docker-compose.app.local.yml up -d --build
```

后端用 `Dockerfile.local`（含 torch/FlagEmbedding），`RAG_EMBEDDING_MODE=local`，在进程内用
CPU 做嵌入/重排。**查询很轻**；但大文档灌库在 CPU 上慢，推荐配合下面的「知识库迁移」：
重活在 GPU 机上灌，灌好导出再导入本机。前端右上角的「嵌入：本地/GPU 机」徽标可确认当前模式。

## 知识库迁移（灌好之后搬过去）

向量灌进 Qdrant 后即与嵌入解耦，可整包搬到另一台机器**无需重新嵌入**。底层用 Qdrant 快照：

1. **任意 GPU 机**上正常灌库（api 模式，重活交给 GPU）。
2. 「文档管理」里该文档点 **导出知识库** → 下载 `<collection>.kb.zip`
   （内含 Qdrant 快照 + 切分参数/分析 + 原文档）。
3. 到目标机（如 N100）前端「文档管理」点 **导入知识库** → 选这个 zip →
   目标 Qdrant 原样重建该 collection，文档列表立即显示「已灌库」，MCP 可直接检索。

> 两端 Qdrant 用同一镜像 tag、嵌入同为 BGE-M3（本项目固定），即可即插即用。
> 局域网内两台 Qdrant 互通时，也可改用快照远程恢复一键直推（后续可加）。

对应接口：`GET /api/kb/{collection}/export`、`POST /api/kb/import`。

## 嵌入模式（api / local 二选一）

后端通过 `RAG_EMBEDDING_MODE` 切换嵌入来源，**检索/灌库逻辑完全一致**：

| 模式 | 行为 | 适用 |
|------|------|------|
| `api`（默认） | 后端 HTTP 调 110.3 的 GPU 服务做嵌入/重排 | N100 算力弱、想用独立 GPU 机 |
| `local` | 后端进程内直接跑 BGE-M3 + reranker | N100 CPU 勉强够用、不想多维护一个服务 |

```bash
# local 模式：先装可选依赖组（torch/FlagEmbedding），再设环境变量启动
cd backend && uv sync --extra local
RAG_EMBEDDING_MODE=local uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> local 模式下查询很快；大文档灌库在 N100 CPU 上会明显慢于 GPU，建议大批量灌库时临时切回 api 模式（或用 CLI `ingest.py` 在 GPU 机上灌）。两种模式写入 Qdrant 的向量结构一致，可混用。

## 关键设计

- **混合检索**：BGE-M3 同时产稠密(1024)+稀疏向量，Qdrant 用命名向量存储，检索时 RRF 融合，再用 reranker 精排。
- **嵌入可切换**：`RAG_EMBEDDING_MODE=api|local`，重依赖（torch/FlagEmbedding）为可选组，api 模式后端镜像保持轻量。
- **切分参数**：每文档可设 chunk_size/overlap/separators/前置标题路径 + 回答 prompt，前端手动填写或由外部 Agent 经接口提供（`PUT /api/chunking/params/{filename}`）。
- 依赖一律用 `uv add` / `uv remove` 管理，保持 pyproject.toml 与 uv.lock 同步。
