"""API 请求/响应模型。"""
from __future__ import annotations

from pydantic import BaseModel


class ChunkParams(BaseModel):
    chunk_size: int = 1000
    chunk_overlap: int = 150
    separators: list[str] | None = None
    prepend_heading_path: bool = False


class ParamsIn(BaseModel):
    """前端手动保存某文档的切分参数（可选附带回答风格）。"""
    params: ChunkParams = ChunkParams()
    collection: str | None = None
    answer_prompt: str | None = None


class IngestIn(BaseModel):
    filename: str
    collection: str | None = None        # 缺省由文件名派生
    params: ChunkParams = ChunkParams()


class SearchIn(BaseModel):
    collection: str
    query: str
    limit: int = 5
    rerank: bool = True
    rerank_pool: int = 20                 # 重排前先混合召回的候选数
