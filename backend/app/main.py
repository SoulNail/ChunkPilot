"""主应用后端入口（部署到 192.168.110.51）。

职责：文档管理 + 每文档切分/嵌入参数 + 灌库 + 调试检索。
切分参数由前端手动填写或由外部 Agent（hermes 等）经接口提供，不在本服务内调用第三方 LLM。
对外的检索能力通过挂载在 /mcp 的 MCP Server 暴露给第三方 Agent。
真正的问答不在本服务内发生。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.mcp_server import mcp
from app.routers import chunking, documents, ingest, kb, search

# 先构建 MCP 的 ASGI 子应用（这一步会创建 session_manager）
_mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MCP 的 streamable-http 会话管理器需在应用生命周期内运行
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="RAG 文档与切分参数管理平台 · 后端", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 内网单用户，开发期放开；生产可收紧
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (documents.router, chunking.router,
          ingest.router, search.router, kb.router):
    app.include_router(r)

# 第三方 Agent 的检索入口：http://<host>:8000/mcp
app.mount("/mcp", _mcp_app)


@app.get("/api/health")
def health() -> dict:
    from app.config import settings
    from app.services import embedding
    try:
        emb = embedding.health()
    except Exception as e:  # noqa: BLE001
        emb = {"error": str(e)}
    return {
        "status": "ok",
        "embedding_mode": settings.embedding_mode,   # api=调GPU机 / local=进程内
        "embedding_service": emb,
        "mcp_endpoint": "/mcp",
    }
