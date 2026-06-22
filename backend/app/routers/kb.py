"""知识库迁移：把一个已灌库的 collection 整包导出 / 在另一台机器导入。

用 Qdrant 快照搬运向量本体（无需重新嵌入），bundle(.zip) 内含：
  - collection.snapshot   Qdrant 快照（向量 + payload + collection 配置）
  - meta.json             该文档的切分/嵌入参数、分析结果、目标 collection 名等
  - source/<原文件>       原始文档（可选，便于目标机也显示/管理这份文档）

典型用法：在任意 GPU 机上灌好 → 「导出知识库」下载 zip → 在 N100 前端「导入知识库」
上传 → 目标 Qdrant 原样重建，文档列表直接显示「已灌库」。
"""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.services import doc_meta, docs, qdrant_store

router = APIRouter(prefix="/api/kb", tags=["kb"])


def _doc_for_collection(collection: str) -> dict | None:
    """在文档列表里找到归属此 collection 的文档（可能没有，如 CLI 直接灌的库）。"""
    for d in docs.list_docs():
        if d["collection"] == collection:
            return d
    return None


@router.get("/{collection}/export")
def export_kb(collection: str) -> FileResponse:
    if collection not in qdrant_store.list_collections():
        raise HTTPException(404, "知识库（collection）不存在")

    tmpdir = Path(tempfile.mkdtemp(prefix="kbexp_"))
    snap_path = tmpdir / "collection.snapshot"
    snapshot = qdrant_store.create_snapshot(collection)
    try:
        qdrant_store.download_snapshot(collection, snapshot, snap_path)
    finally:
        # 下载完即删源端快照，避免在源 Qdrant 上堆积
        qdrant_store.delete_snapshot(collection, snapshot)

    d = _doc_for_collection(collection)
    meta = {
        "collection": collection,
        "doc_name": d["name"] if d else None,
        "params": d.get("params") if d else None,
        "analysis": d.get("analysis") if d else None,
        "points_count": d.get("points_count") if d else None,
    }

    zip_path = tmpdir / f"{collection}.kb.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as z:
        z.write(snap_path, "collection.snapshot")          # 快照已是压缩包，存储模式即可
        z.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
        if d:
            src = docs.doc_path(d["name"])
            if src.is_file():
                z.write(src, f"source/{d['name']}")

    return FileResponse(
        zip_path,
        filename=f"{collection}.kb.zip",
        media_type="application/zip",
        background=BackgroundTask(shutil.rmtree, tmpdir, ignore_errors=True),
    )


@router.post("/import")
async def import_kb(file: UploadFile) -> dict:
    data = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise HTTPException(400, "不是有效的 zip 包")

    with zf:
        names = set(zf.namelist())
        if "meta.json" not in names or "collection.snapshot" not in names:
            raise HTTPException(400, "无效的知识库包（缺 meta.json 或 collection.snapshot）")
        meta = json.loads(zf.read("meta.json").decode("utf-8"))
        collection = meta.get("collection")
        if not collection:
            raise HTTPException(400, "知识库包缺少 collection 名")

        # 快照写到临时文件再上传恢复（避免大文件全量驻留内存）
        tmpdir = Path(tempfile.mkdtemp(prefix="kbimp_"))
        try:
            snap_path = tmpdir / "collection.snapshot"
            snap_path.write_bytes(zf.read("collection.snapshot"))
            qdrant_store.restore_snapshot(collection, snap_path)

            doc_name = meta.get("doc_name")
            wrote_doc = False
            if doc_name:
                member = f"source/{doc_name}"
                if member in names:
                    # 经 doc_path 清洗，杜绝 zip 路径穿越
                    docs.doc_path(doc_name).write_bytes(zf.read(member))
                    wrote_doc = True
                doc_meta.update(
                    doc_name,
                    collection=collection,
                    params=meta.get("params"),
                    analysis=meta.get("analysis"),
                    status="done",
                    points_count=meta.get("points_count"),
                    error="",
                )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    count = qdrant_store.collection_info(collection)["points_count"]
    return {
        "collection": collection,
        "doc_name": meta.get("doc_name"),
        "wrote_doc": wrote_doc,
        "points_count": count,
    }
