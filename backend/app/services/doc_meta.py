"""每个文档的「切分/嵌入参数 + 分析结果 + 灌库状态」持久化。

这是本平台的核心：前端不是问答产品，而是管理「各文档用什么参数切片/嵌入、
灌进哪个知识库、当前状态如何」。真正的检索问答由外部 Agent 经 MCP 完成。

存储用单个 JSON 文件（单用户、量小），按安全文件名为 key。线程安全
（灌库任务在后台线程里更新状态）。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from app.config import settings

_lock = threading.RLock()


def _path():
    return settings.data_dir / "doc_meta.json"


def _load() -> dict:
    p = _path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    tmp = _path().with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_path())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get(name: str) -> dict | None:
    with _lock:
        return _load().get(name)


def all_meta() -> dict:
    with _lock:
        return _load()


def update(name: str, **fields) -> dict:
    """读-改-写合并。fields 里非 None 的键覆盖原值。"""
    with _lock:
        data = _load()
        entry = data.get(name, {})
        for k, v in fields.items():
            if v is not None:
                entry[k] = v
        entry["updated_at"] = _now()
        data[name] = entry
        _save(data)
        return entry


def remove(name: str) -> None:
    with _lock:
        data = _load()
        if name in data:
            del data[name]
            _save(data)
