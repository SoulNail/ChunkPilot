"""本地嵌入提供者：进程内跑 BGE-M3 + reranker。

仅 RAG_EMBEDDING_MODE=local 时使用；依赖（torch/FlagEmbedding）为可选组，
通过 `uv sync --extra local` 安装。返回结构与 API 模式完全一致。
"""
from __future__ import annotations

import threading

from app.config import settings

_lock = threading.Lock()
_embedder = None
_reranker = None


def _use_fp16() -> bool:
    import torch
    return torch.cuda.is_available()


def _get_embedder():
    global _embedder
    if _embedder is None:
        with _lock:
            if _embedder is None:
                from FlagEmbedding import BGEM3FlagModel
                _embedder = BGEM3FlagModel(settings.local_embed_model, use_fp16=_use_fp16())
    return _embedder


def _get_reranker():
    global _reranker
    if _reranker is None:
        with _lock:
            if _reranker is None:
                from FlagEmbedding import FlagReranker
                _reranker = FlagReranker(settings.local_rerank_model, use_fp16=_use_fp16())
    return _reranker


def health() -> dict:
    import torch
    return {
        "status": "ok", "mode": "local",
        "cuda": torch.cuda.is_available(),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "embed_model": settings.local_embed_model,
        "rerank_model": settings.local_rerank_model,
    }


def embed(texts: list[str], kind: str = "doc") -> tuple[list[list[float]], list[dict]]:
    out = _get_embedder().encode(
        texts, return_dense=True, return_sparse=True, return_colbert_vecs=False
    )
    dense = [v.tolist() for v in out["dense_vecs"]]
    sparse = []
    for lw in out["lexical_weights"]:
        items = {int(t): float(w) for t, w in lw.items() if float(w) > 0.0}
        sparse.append({"indices": list(items.keys()), "values": list(items.values())})
    return dense, sparse


def rerank(query: str, documents: list[str], top_k: int | None = None) -> dict:
    if not documents:
        return {"scores": [], "order": []}
    scores = _get_reranker().compute_score([[query, d] for d in documents], normalize=True)
    if isinstance(scores, float):
        scores = [scores]
    scores = [float(s) for s in scores]
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    if top_k is not None:
        order = order[:top_k]
    return {"scores": scores, "order": order}
