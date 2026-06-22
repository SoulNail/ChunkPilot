"""切分参数：前端手动填写或外部 Agent 经接口提供，保存到文档元数据。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import ParamsIn
from app.services import doc_meta, docs

router = APIRouter(prefix="/api/chunking", tags=["chunking"])


@router.put("/params/{filename}")
def save_params(filename: str, body: ParamsIn) -> dict:
    """前端手动编辑后保存某文档的切分参数（不经 LLM）。"""
    p = docs.doc_path(filename)
    if not p.is_file():
        raise HTTPException(404, "文件不存在")
    analysis = None
    if body.answer_prompt is not None:
        analysis = {**((doc_meta.get(p.name) or {}).get("analysis") or {}),
                    "suggested_answer_prompt": body.answer_prompt}
    entry = doc_meta.update(p.name, params=body.params.model_dump(),
                            collection=body.collection, analysis=analysis)
    return {"name": p.name, **entry}
