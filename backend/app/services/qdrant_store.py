"""Qdrant 存储：命名向量（稠密+稀疏）建库、灌库、混合检索（RRF 融合）、快照迁移。"""
from __future__ import annotations

import uuid
from pathlib import Path

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Fusion,
    FusionQuery,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from app.config import settings

DENSE = "dense"
SPARSE = "sparse"
DENSE_SIZE = 1024


def client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def list_collections() -> list[str]:
    return [c.name for c in client().get_collections().collections]


def collections_with_counts() -> dict[str, int]:
    """{collection 名: 向量条数}。用于核对文档是否真的已灌库。"""
    c = client()
    out: dict[str, int] = {}
    for col in c.get_collections().collections:
        try:
            out[col.name] = c.get_collection(collection_name=col.name).points_count or 0
        except Exception:  # noqa: BLE001
            out[col.name] = 0
    return out


def recreate_collection(name: str) -> None:
    client().recreate_collection(
        collection_name=name,
        vectors_config={DENSE: VectorParams(size=DENSE_SIZE, distance=Distance.COSINE)},
        sparse_vectors_config={SPARSE: SparseVectorParams()},
    )


def delete_collection(name: str) -> None:
    client().delete_collection(collection_name=name)


def collection_info(name: str) -> dict:
    info = client().get_collection(collection_name=name)
    return {"name": name, "points_count": info.points_count}


def upsert(
    name: str,
    records: list[dict],
    dense: list[list[float]],
    sparse: list[dict],
    batch: int = 256,
) -> None:
    c = client()
    for i in range(0, len(records), batch):
        pts = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector={
                    DENSE: d,
                    SPARSE: SparseVector(indices=s["indices"], values=s["values"]),
                },
                payload=r,
            )
            for r, d, s in zip(
                records[i:i + batch], dense[i:i + batch], sparse[i:i + batch]
            )
        ]
        c.upsert(collection_name=name, points=pts)


# ---- 快照迁移：把一个 collection 整包（向量+payload+配置）搬到另一台 Qdrant ----

def _base() -> str:
    return settings.qdrant_url.rstrip("/")


def create_snapshot(name: str) -> str:
    """在源 Qdrant 上为 collection 生成快照，返回快照文件名。"""
    r = httpx.post(f"{_base()}/collections/{name}/snapshots", timeout=600.0)
    r.raise_for_status()
    return r.json()["result"]["name"]


def download_snapshot(name: str, snapshot: str, dest: Path) -> None:
    """把快照文件流式下载到本地 dest（不全量载入内存）。"""
    with httpx.stream(
        "GET", f"{_base()}/collections/{name}/snapshots/{snapshot}", timeout=600.0
    ) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)


def delete_snapshot(name: str, snapshot: str) -> None:
    """删除源 Qdrant 上的快照文件，避免堆积（失败忽略）。"""
    try:
        httpx.delete(f"{_base()}/collections/{name}/snapshots/{snapshot}", timeout=120.0)
    except Exception:  # noqa: BLE001
        pass


def restore_snapshot(name: str, path: Path) -> None:
    """把本地快照文件上传恢复到目标 Qdrant，按快照内容（重新）创建该 collection。"""
    with open(path, "rb") as f:
        r = httpx.post(
            f"{_base()}/collections/{name}/snapshots/upload",
            params={"priority": "snapshot"},
            files={"snapshot": (path.name, f, "application/octet-stream")},
            timeout=600.0,
        )
    r.raise_for_status()


def hybrid_search(
    name: str,
    dense_q: list[float],
    sparse_q: dict,
    limit: int = 20,
) -> list[dict]:
    """稠密 + 稀疏各召回，RRF 融合。返回 [{score, payload}, ...]。"""
    res = client().query_points(
        collection_name=name,
        prefetch=[
            Prefetch(query=dense_q, using=DENSE, limit=limit),
            Prefetch(
                query=SparseVector(indices=sparse_q["indices"], values=sparse_q["values"]),
                using=SPARSE,
                limit=limit,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
    return [{"score": p.score, "payload": p.payload} for p in res.points]
