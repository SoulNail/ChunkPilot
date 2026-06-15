"""灌库：启动后台任务 + SSE 进度。"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.schemas import IngestIn
from app.services import doc_meta, docs, ingest_job

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("")
def start(req: IngestIn) -> dict:
    p = docs.doc_path(req.filename)
    if not p.is_file():
        raise HTTPException(404, "文件不存在")
    collection = req.collection or docs.collection_for(req.filename)
    params = req.params.model_dump()
    # 记录本次灌库用的参数与目标库，状态置为进行中
    doc_meta.update(p.name, params=params, collection=collection,
                    status="ingesting", error="")
    job_id = ingest_job.start(p, collection, params)
    return {"job_id": job_id, "collection": collection}


@router.get("/{job_id}/stream")
async def stream(job_id: str) -> EventSourceResponse:
    if ingest_job.get_job(job_id) is None:
        raise HTTPException(404, "任务不存在")

    async def gen():
        while True:
            job = ingest_job.get_job(job_id)
            if job is None:
                break
            yield {"data": json.dumps(job, ensure_ascii=False)}
            if job["status"] in ("done", "error"):
                break
            await asyncio.sleep(0.5)

    return EventSourceResponse(gen())
