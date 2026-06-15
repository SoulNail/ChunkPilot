"""GPU 推理服务 (部署到 192.168.110.3)。

提供 /embed (稠密+稀疏) 与 /rerank，供主应用 (192.168.110.51) 调用。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI
from pydantic import BaseModel

import models


# ---------- 请求/响应模型 ----------
class EmbedRequest(BaseModel):
    texts: list[str]
    kind: str = "doc"          # "doc" | "query"（当前对称，预留区分）


class SparseVector(BaseModel):
    indices: list[int]
    values: list[float]


class EmbedResponse(BaseModel):
    dense: list[list[float]]
    sparse: list[SparseVector]


class RerankRequest(BaseModel):
    query: str
    documents: list[str]
    top_k: int | None = None


class RerankResponse(BaseModel):
    scores: list[float]        # 与输入 documents 对齐
    order: list[int]           # 按分数降序的下标；若给 top_k 则截断


@asynccontextmanager
async def lifespan(app: FastAPI):
    models.warmup()            # 启动即加载模型到显存
    yield


app = FastAPI(title="RAG Embedding/Rerank Service", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "cuda": torch.cuda.is_available(),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "embed_model": models.EMBED_MODEL_NAME,
        "rerank_model": models.RERANK_MODEL_NAME,
    }


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest) -> EmbedResponse:
    dense, sparse = models.embed(req.texts)
    sparse_out = [
        SparseVector(indices=list(d.keys()), values=list(d.values())) for d in sparse
    ]
    return EmbedResponse(dense=dense, sparse=sparse_out)


@app.post("/rerank", response_model=RerankResponse)
def rerank(req: RerankRequest) -> RerankResponse:
    scores = models.rerank(req.query, req.documents)
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    if req.top_k is not None:
        order = order[: req.top_k]
    return RerankResponse(scores=scores, order=order)
