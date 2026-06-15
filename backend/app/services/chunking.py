"""切分逻辑（移植自 CLI ingest.py，参数化以接收 LLM 给出的方案）。"""
from __future__ import annotations

import re

# 拼接文档里每个源文件的分隔标记：====\nFILE: 路径\n====
FILE_MARKER = re.compile(r"^=+\nFILE: (.*?)\n=+\n", re.M)
DEFAULT_SEPARATORS = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " "]
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def split_into_files(text: str) -> list[tuple[str, str]]:
    """把拼接文档按 FILE 标记拆成 [(源文件路径, 内容), ...]；无标记则返回空。"""
    parts = FILE_MARKER.split(text)
    out: list[tuple[str, str]] = []
    for i in range(1, len(parts), 2):
        path, content = parts[i].strip(), parts[i + 1].strip()
        if content:
            out.append((path, content))
    return out


def recursive_split(text: str, seps: list[str], chunk_size: int) -> list[str]:
    """递归按分隔符切分到 <= chunk_size。"""
    if len(text) <= chunk_size:
        return [text]
    if not seps:
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    sep, rest = seps[0], seps[1:]
    pieces: list[str] = []
    buf = ""
    for seg in text.split(sep):
        candidate = seg if not buf else buf + sep + seg
        if len(candidate) <= chunk_size:
            buf = candidate
        else:
            if buf:
                pieces.append(buf)
            pieces.extend(
                recursive_split(seg, rest, chunk_size) if len(seg) > chunk_size else [seg]
            )
            buf = ""
    if buf:
        pieces.append(buf)
    return pieces


def add_overlap(chunks: list[str], overlap: int) -> list[str]:
    if overlap <= 0 or len(chunks) <= 1:
        return chunks
    out = [chunks[0]]
    for prev, cur in zip(chunks, chunks[1:]):
        out.append(prev[-overlap:] + cur)
    return out


def _heading_path(text: str) -> str:
    """取一段文本里最后出现的标题层级路径，如 'A > B > C'。"""
    stack: dict[int, str] = {}
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            stack[level] = m.group(2).strip()
            # 清掉更深层级
            for k in list(stack):
                if k > level:
                    del stack[k]
    return " > ".join(stack[k] for k in sorted(stack)) if stack else ""


def chunk_document(
    text: str,
    *,
    doc_name: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    separators: list[str] | None = None,
    prepend_heading_path: bool = False,
) -> list[dict]:
    """把整篇文档切成带元数据的块。返回 [{source, doc, chunk_index, text}, ...]。"""
    seps = separators or DEFAULT_SEPARATORS
    files = split_into_files(text) or [(doc_name, text)]
    records: list[dict] = []
    for source, content in files:
        chunks = add_overlap(recursive_split(content, seps, chunk_size), chunk_overlap)
        for idx, chunk in enumerate(chunks):
            chunk = chunk.strip()
            if len(chunk) < 20:
                continue
            stored = chunk
            if prepend_heading_path:
                hp = _heading_path(chunk)
                if hp:
                    stored = f"[{source} · {hp}]\n{chunk}"
            records.append(
                {"source": source, "doc": doc_name, "chunk_index": idx, "text": stored}
            )
    return records
