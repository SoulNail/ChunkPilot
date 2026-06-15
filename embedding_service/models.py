"""GPU 推理：BGE-M3 稠密+稀疏嵌入、bge-reranker 重排。模型常驻显存，进程内单例。"""
from __future__ import annotations

import threading

import torch
from FlagEmbedding import BGEM3FlagModel, FlagReranker

EMBED_MODEL_NAME = "BAAI/bge-m3"
RERANK_MODEL_NAME = "BAAI/bge-reranker-v2-m3"

_lock = threading.Lock()
_embedder: BGEM3FlagModel | None = None
_reranker: FlagReranker | None = None


def _use_fp16() -> bool:
    return torch.cuda.is_available()


def get_embedder() -> BGEM3FlagModel:
    global _embedder
    if _embedder is None:
        with _lock:
            if _embedder is None:
                _embedder = BGEM3FlagModel(EMBED_MODEL_NAME, use_fp16=_use_fp16())
    return _embedder


def get_reranker() -> FlagReranker:
    global _reranker
    if _reranker is None:
        with _lock:
            if _reranker is None:
                _reranker = FlagReranker(RERANK_MODEL_NAME, use_fp16=_use_fp16())
    return _reranker


def embed(texts: list[str]) -> tuple[list[list[float]], list[dict[int, float]]]:
    """返回 (稠密向量列表, 稀疏向量列表)。稀疏为 {token_id(int): weight(float)}。"""
    out = get_embedder().encode(
        texts,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )
    dense = [v.tolist() for v in out["dense_vecs"]]
    # lexical_weights: list[dict[str, float]] → 键转 int，丢弃 0 权重
    sparse = [
        {int(tok): float(w) for tok, w in lw.items() if float(w) > 0.0}
        for lw in out["lexical_weights"]
    ]
    return dense, sparse


def rerank(query: str, documents: list[str]) -> list[float]:
    """返回每个 document 对 query 的相关性分数（已归一化到 0~1）。"""
    if not documents:
        return []
    pairs = [[query, d] for d in documents]
    scores = get_reranker().compute_score(pairs, normalize=True)
    # 单条时可能返回标量
    if isinstance(scores, float):
        return [scores]
    return [float(s) for s in scores]


def warmup() -> None:
    """启动时预加载模型，避免首个请求超时。"""
    embed(["warmup"])
    rerank("warmup", ["warmup"])
