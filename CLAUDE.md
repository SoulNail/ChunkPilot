# CLAUDE.md — ChunkPilot 项目指令

## ⭐ 首要规则：每次对话后更新 notes
**每单次对话结束时，只要本次做了重要改动（新功能 / 改接口 / 调部署 / 重要决策 / 临时操作步骤），就必须更新 `notes/`。**
- `notes/` 是本机工作笔记，已在 `.gitignore` 忽略，**不上传 GitHub**，专门用来跨会话/跨模型恢复上下文。
- 至少更新 `notes/worklog.md`（已完成/进行中/待办）；涉及背景或测试步骤的，相应更新 `notes/project-context.md`、`notes/dev-test-setup.md`。
- 只记代码/README/git 里看不出来的东西，别重复仓库已有信息。

## 项目定位
ChunkPilot 是 **RAG 知识库管理后台**，不是问答产品。切分/嵌入参数由前端**手动填写**，或后续由 hermes agent 经接口提供（应用内第三方 LLM 自动判参的「LLM 配置」页已删除）。真正问答由外部 Agent（hermes / claude code / opencode）经 **MCP**（后端 `/mcp`，Streamable HTTP）连进来自行完成。

## 部署拓扑 & 端口
- **192.168.110.51（N100，弱 CPU，最终部署目标）**：前端 + 后端 + Qdrant。前端对外口 **22180**。
- **192.168.110.3（RTX 3060Ti，开发/GPU 机）**：`embedding_service`（嵌入+重排，:8001），灌库重活在此。
- 后端 :8000，Qdrant :6333。GitHub：https://github.com/SoulNail/ChunkPilot.git

## 嵌入模式（启动时 env 决定，非运行时 UI 开关）
- `RAG_EMBEDDING_MODE=api`（默认）：后端 HTTP 调 110.3 GPU 服务，镜像轻量。
- `RAG_EMBEDDING_MODE=local`：进程内跑 BGE-M3+reranker，需 `Dockerfile.local` / `uv sync --extra local`。
- 三套 compose：`docker-compose.gpu.yml`(110.3) / `docker-compose.app.yml`(110.51,api) / `docker-compose.app.local.yml`(单机,local)。

## 关键设计
- 检索：BGE-M3 混合（稠密 1024 Cosine + 稀疏命名向量），RRF 融合，再 bge-reranker-v2-m3 精排。
- 知识库迁移：Qdrant 快照导出/导入 `.kb.zip`，跨机搬运**无需重嵌入**（`GET /api/kb/{collection}/export`、`POST /api/kb/import`）。

## 红线 / 约定
- Python 一律 **uv**：`uv venv` / `uv run` / `uv add` / `uv remove`。禁止 pip、手改 pyproject deps、venv/poetry/conda。
- 任何密钥/敏感信息只存后端进程内，**不回传明文、不写日志**（注：原 LLM api_key 配置已随「LLM 配置」页删除）。
- 用**中文**回复。commit message 结尾带 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- 本机是 **podman**（非 docker）；`localhost` 走 IPv6，访问/端口映射用 `127.0.0.1`。

> 更详细的背景、测试脚本、进展见本机 `notes/`（不入库）。
