"""混合检索（稠密+稀疏 RRF） + 可选重排序。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import SearchIn
from app.services import embedding, qdrant_store

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/collections")
def collections() -> list[str]:
    return qdrant_store.list_collections()


def run_search(req: SearchIn) -> list[dict]:
    dense_q, sparse_q = embedding.embed_one(req.query, kind="query")
    pool = max(req.limit, req.rerank_pool if req.rerank else req.limit)
    hits = qdrant_store.hybrid_search(req.collection, dense_q, sparse_q, limit=pool)

    if req.rerank and hits:
        docs_text = [h["payload"]["text"] for h in hits]
        rr = embedding.rerank(req.query, docs_text, top_k=req.limit)
        results = []
        for idx in rr["order"]:
            h = hits[idx]
            results.append({
                "score": rr["scores"][idx],
                "source": h["payload"].get("source"),
                "doc": h["payload"].get("doc"),
                "text": h["payload"]["text"],
            })
        return results

    return [
        {"score": h["score"], "source": h["payload"].get("source"),
         "doc": h["payload"].get("doc"), "text": h["payload"]["text"]}
        for h in hits[:req.limit]
    ]


@router.post("")
def search(req: SearchIn) -> list[dict]:
    try:
        return run_search(req)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"检索失败：{e}")
