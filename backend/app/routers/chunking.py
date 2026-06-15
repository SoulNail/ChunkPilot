"""LLM 切分分析：提取文档画像 → LLM 给出结构化切分方案。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import AnalyzeIn, ParamsIn
from app.services import doc_meta, doc_profile, docs, llm

router = APIRouter(prefix="/api/chunking", tags=["chunking"])

_PARAM_KEYS = ("chunk_size", "chunk_overlap", "separators", "prepend_heading_path")


@router.post("/analyze")
def analyze(req: AnalyzeIn) -> dict:
    p = docs.doc_path(req.filename)
    if not p.is_file():
        raise HTTPException(404, "文件不存在")
    text = p.read_text(encoding="utf-8", errors="ignore")
    profile = doc_profile.build_profile(text, p.name)
    try:
        plan = llm.analyze_chunking(profile)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"LLM 分析失败：{e}")
    # 附带画像里对前端有用的统计
    plan["_profile"] = {
        k: profile[k] for k in
        ("char_count", "language", "heading_count", "code_fence_count", "table_row_count")
    }
    # 落库：LLM 给的参数与分析说明，作为该文档的默认切分方案（前端可改）
    params = {k: plan[k] for k in _PARAM_KEYS if k in plan}
    analysis = {k: plan.get(k) for k in
                ("doc_type", "language", "strategy", "reasoning", "suggested_answer_prompt")}
    doc_meta.update(p.name, params=params, analysis=analysis)
    return plan


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
