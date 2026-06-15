"""提取「文档画像」喂给 LLM，避免发送全文。"""
from __future__ import annotations

import re

CJK_RE = re.compile(r"[一-鿿]")
HEADING_RE = re.compile(r"^#{1,6}\s+", re.M)
CODE_FENCE_RE = re.compile(r"^```", re.M)
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.M)


def build_profile(text: str, filename: str) -> dict:
    n = len(text)
    cjk = len(CJK_RE.findall(text[:20000]))
    lang = "zh" if cjk > 200 else "en"

    head_sample = text[:2000]
    mid = text[n // 2: n // 2 + 1500] if n > 4000 else ""

    return {
        "filename": filename,
        "ext": filename.rsplit(".", 1)[-1].lower() if "." in filename else "",
        "char_count": n,
        "language": lang,
        "heading_count": len(HEADING_RE.findall(text)),
        "code_fence_count": len(CODE_FENCE_RE.findall(text)),
        "table_row_count": len(TABLE_ROW_RE.findall(text)),
        "has_file_markers": "FILE:" in head_sample or "\nFILE: " in text[:5000],
        "head_sample": head_sample,
        "mid_sample": mid,
    }
