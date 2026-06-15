"""LLM 配置与连通测试。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import LLMConfigIn
from app.services import llm

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/config")
def get_config() -> dict:
    return llm.get_config_masked()


@router.post("/config")
def set_config(cfg: LLMConfigIn) -> dict:
    llm.set_config(cfg.base_url, cfg.api_key, cfg.model)
    return llm.get_config_masked()


@router.post("/test")
def test() -> dict:
    try:
        return llm.test_connection()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"连通失败：{e}")
