"""嵌入/重排统一入口。按 RAG_EMBEDDING_MODE 分派到 api(调110.3) 或 local(进程内)。

公开函数签名与返回结构在两种模式下完全一致：
- embed(texts)  -> (dense: list[list[float]], sparse: list[{"indices","values"}])
- rerank(query, docs, top_k) -> {"scores": [...], "order": [...]}
"""
from __future__ import annotations

import httpx

from app.config import settings


def _is_local() -> bool:
    return settings.embedding_mode == "local"


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.embedding_service_url, timeout=settings.request_timeout)


def health() -> dict:
    if _is_local():
        from app.services import local_embed
        return local_embed.health()
    with _client() as c:
        return c.get("/health").json()


def embed(texts: list[str], kind: str = "doc") -> tuple[list[list[float]], list[dict]]:
    if _is_local():
        from app.services import local_embed
        return local_embed.embed(texts, kind=kind)

    dense_all: list[list[float]] = []
    sparse_all: list[dict] = []
    with _client() as c:
        for i in range(0, len(texts), settings.embed_batch):
            batch = texts[i:i + settings.embed_batch]
            r = c.post("/embed", json={"texts": batch, "kind": kind})
            r.raise_for_status()
            data = r.json()
            dense_all.extend(data["dense"])
            sparse_all.extend(data["sparse"])
    return dense_all, sparse_all


def embed_one(text: str, kind: str = "query") -> tuple[list[float], dict]:
    dense, sparse = embed([text], kind=kind)
    return dense[0], sparse[0]


def rerank(query: str, documents: list[str], top_k: int | None = None) -> dict:
    if not documents:
        return {"scores": [], "order": []}
    if _is_local():
        from app.services import local_embed
        return local_embed.rerank(query, documents, top_k)
    with _client() as c:
        r = c.post("/rerank", json={"query": query, "documents": documents, "top_k": top_k})
        r.raise_for_status()
        return r.json()
