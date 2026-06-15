"""文档管理：列表 / 上传 / 下载 / 删除。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.services import docs

router = APIRouter(prefix="/api/docs", tags=["documents"])


@router.get("")
def list_docs() -> list[dict]:
    return docs.list_docs()


@router.post("")
async def upload(file: UploadFile) -> dict:
    data = await file.read()
    return docs.save(file.filename or "unnamed", data)


@router.get("/{filename}")
def download(filename: str) -> FileResponse:
    p = docs.doc_path(filename)
    if not p.is_file():
        raise HTTPException(404, "文件不存在")
    return FileResponse(p, filename=p.name)


@router.delete("/{filename}")
def delete(filename: str) -> dict:
    if not docs.delete(filename):
        raise HTTPException(404, "文件不存在")
    return {"deleted": filename}
