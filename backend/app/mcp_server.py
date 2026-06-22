"""MCP Server（Streamable HTTP）—— 给外部 Agent 用的检索后端。

本平台的「问答」不在这里发生：opencode / claude code / hermes 这类 Agent 通过
MCP 连到这里，调用下面的工具去查 Qdrant（混合检索 + 重排），拿回片段后自己组织
回答。前端只管文档与切分/嵌入参数；检索能力统一从这里对外暴露。

挂载在后端同进程的 `/mcp` 路径下，复用 app.services 里的嵌入/检索逻辑。
Agent 连接地址：http://<部署IP>:8000/mcp
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.schemas import SearchIn
from app.services import doc_meta, qdrant_store
from app.routers.search import run_search

mcp = FastMCP(
    "rag-qdrant",
    instructions=(
        "RAG 知识库检索后端。先用 list_knowledge_bases 看有哪些知识库及其用途，"
        "再用 search_documents 在指定知识库里检索，返回最相关的文档片段。"
    ),
    stateless_http=True,
    streamable_http_path="/",
)


@mcp.tool()
def list_knowledge_bases() -> list[dict]:
    """列出所有可检索的知识库（Qdrant collection）及其元信息。

    返回每个知识库的：collection 名、向量条数、来源文档、文档类型/语言，
    以及该库建议的回答风格（answer_prompt，由前端或 Agent 灌库时设定）。
    Agent 应据此决定该在哪个库里检索。
    """
    # collection 名 -> 来源文档元数据
    by_collection: dict[str, dict] = {}
    for name, meta in doc_meta.all_meta().items():
        col = meta.get("collection")
        if col:
            by_collection[col] = {"source_doc": name, **meta}

    out = []
    for col in qdrant_store.list_collections():
        info = qdrant_store.collection_info(col)
        meta = by_collection.get(col, {})
        analysis = meta.get("analysis") or {}
        out.append({
            "collection": col,
            "points_count": info.get("points_count"),
            "source_doc": meta.get("source_doc"),
            "doc_type": analysis.get("doc_type"),
            "language": analysis.get("language"),
            "answer_prompt": analysis.get("suggested_answer_prompt"),
        })
    return out


@mcp.tool()
def search_documents(
    query: str,
    collection: str,
    top_k: int = 5,
    rerank: bool = True,
) -> list[dict]:
    """在指定知识库中检索与 query 最相关的文档片段。

    用 BGE-M3 稠密+稀疏向量混合检索（RRF 融合），可选 reranker 精排。
    返回 [{score, source, doc, text}, ...]，按相关性降序。

    参数：
    - query: 检索问题/关键词
    - collection: 知识库名（来自 list_knowledge_bases）
    - top_k: 返回片段数，默认 5
    - rerank: 是否用重排序模型精排，默认 True（质量更高，略慢）
    """
    req = SearchIn(collection=collection, query=query, limit=top_k, rerank=rerank)
    return run_search(req)
