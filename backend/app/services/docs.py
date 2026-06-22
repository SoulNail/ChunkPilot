"""文档存储：直接以 docs_dir 下的文件为准（单用户，MVP 不引入数据库）。"""
from __future__ import annotations

import re
from pathlib import Path

from app.config import settings
from app.services import doc_meta

SAFE_RE = re.compile(r"[^A-Za-z0-9._一-鿿-]")


def safe_name(filename: str) -> str:
    """防路径穿越，仅保留文件名部分并清洗。"""
    base = Path(filename).name
    return SAFE_RE.sub("_", base) or "unnamed"


def doc_path(filename: str) -> Path:
    return settings.docs_dir / safe_name(filename)


def list_docs() -> list[dict]:
    # 实时核对 Qdrant：即便本地没有灌库记录（如早先用 CLI 灌的库），
    # 只要对应 collection 已存在且有向量，也应显示为「已灌库」。
    from app.services import qdrant_store
    try:
        live = qdrant_store.collections_with_counts()
    except Exception:  # noqa: BLE001
        live = {}

    out = []
    claimed: set[str] = set()           # 已被本地原文档「认领」的 collection
    for p in sorted(settings.docs_dir.glob("*")):
        if not p.is_file():
            continue
        # 跳过点文件（如 .gitkeep 占位文件），它们不是用户文档
        if p.name.startswith("."):
            continue
        meta = doc_meta.get(p.name) or {}
        collection = meta.get("collection") or collection_for(p.name)
        claimed.add(collection)
        status = meta.get("status", "new")
        points = meta.get("points_count")
        # 灌库进行中以本地状态为准；否则以 Qdrant 实际存在与否为准
        if status != "ingesting":
            if collection in live and live[collection] > 0:
                status = "done"
                points = live[collection]
            elif status == "done":
                # 记录说已灌库，但 Qdrant 里已不存在 → 回退
                status = "new"
                points = None
        out.append({
            "name": p.name,
            "size_bytes": p.stat().st_size,
            "collection": collection,
            "params": meta.get("params"),
            "analysis": meta.get("analysis"),
            "status": status,                        # new|ingesting|done|error
            "points_count": points,
            "error": meta.get("error"),
            "updated_at": meta.get("updated_at"),
            "has_local_file": True,                  # 本地 docs/ 里有原文档
        })

    # Qdrant 里存在、但本地没有对应原文档的知识库：
    # CLI 直接灌的、导入未带原文的、或原文被删但向量还在的。也要展示出来。
    for col, cnt in sorted(live.items()):
        if col in claimed or cnt <= 0:
            continue
        out.append({
            "name": col,
            "size_bytes": None,
            "collection": col,
            "params": None,
            "analysis": None,
            "status": "done",
            "points_count": cnt,
            "error": None,
            "updated_at": None,
            "has_local_file": False,                 # 只在 Qdrant 里，无本地原文
        })
    return out


def save(filename: str, data: bytes) -> dict:
    p = doc_path(filename)
    p.write_bytes(data)
    return {"name": p.name, "size_bytes": p.stat().st_size, "collection": collection_for(p.name),
            "status": "new"}


def delete(filename: str) -> bool:
    p = doc_path(filename)
    if p.is_file():
        p.unlink()
        doc_meta.remove(p.name)
        return True
    return False


def collection_for(filename: str) -> str:
    """由文件名派生 collection 名（去扩展名 + 清洗）。"""
    stem = Path(filename).stem
    return SAFE_RE.sub("_", stem).strip("_").lower() or "docs"
