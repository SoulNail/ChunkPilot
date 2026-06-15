"""后台灌库任务：切分→分批嵌入(调110.3)→写Qdrant，进度供 SSE 轮询。"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from app.services import chunking, doc_meta, embedding, qdrant_store

# job_id -> 状态
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def get_job(job_id: str) -> dict | None:
    with _lock:
        return dict(_jobs[job_id]) if job_id in _jobs else None


def _set(job_id: str, **kw) -> None:
    with _lock:
        _jobs[job_id].update(**kw)


def _run(job_id: str, doc_path: Path, collection: str, params: dict) -> None:
    try:
        text = doc_path.read_text(encoding="utf-8", errors="ignore")
        records = chunking.chunk_document(text, doc_name=doc_path.name, **params)
        total = len(records)
        _set(job_id, status="running", total=total, done=0)

        qdrant_store.recreate_collection(collection)

        batch = 64
        for i in range(0, total, batch):
            recs = records[i:i + batch]
            dense, sparse = embedding.embed([r["text"] for r in recs], kind="doc")
            qdrant_store.upsert(collection, recs, dense, sparse)
            _set(job_id, done=min(i + batch, total))

        _set(job_id, status="done")
        doc_meta.update(doc_path.name, status="done", points_count=total, error="")
    except Exception as e:  # noqa: BLE001
        _set(job_id, status="error", error=str(e))
        doc_meta.update(doc_path.name, status="error", error=str(e))


def start(doc_path: Path, collection: str, params: dict) -> str:
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {
            "id": job_id, "status": "pending", "total": 0, "done": 0,
            "collection": collection, "error": None,
        }
    threading.Thread(target=_run, args=(job_id, doc_path, collection, params), daemon=True).start()
    return job_id
