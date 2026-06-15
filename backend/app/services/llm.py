"""LLM 服务：OpenAI 兼容客户端（用户自填 base_url/api_key/model）。

本平台里 LLM 只用于「给文档判定切分/嵌入参数」，不做问答（问答由外部 Agent
经 MCP 完成）。所以这里只有连通测试 + 切分分析两个能力。

- 配置存进程内（单用户）；api_key 不回传明文、不写日志。
- 切分分析用 JSON 输出。
"""
from __future__ import annotations

import json

from openai import OpenAI

# 进程内配置（单用户）
_config: dict = {"base_url": "", "api_key": "", "model": ""}


def set_config(base_url: str, api_key: str, model: str) -> None:
    _config.update(base_url=base_url.rstrip("/"), api_key=api_key, model=model)


def get_config_masked() -> dict:
    key = _config["api_key"]
    masked = (key[:4] + "****" + key[-4:]) if len(key) >= 8 else ("****" if key else "")
    return {"base_url": _config["base_url"], "model": _config["model"], "api_key": masked,
            "configured": bool(_config["base_url"] and _config["api_key"] and _config["model"])}


def _client() -> OpenAI:
    if not (_config["base_url"] and _config["api_key"]):
        raise RuntimeError("LLM 未配置：请先在前端填写 base_url / api_key / model")
    return OpenAI(base_url=_config["base_url"], api_key=_config["api_key"])


def test_connection() -> dict:
    """发一条极短请求验证连通。"""
    resp = _client().chat.completions.create(
        model=_config["model"],
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=5,
    )
    return {"ok": True, "model": resp.model}


ANALYZE_SYSTEM = """你是 RAG 切分策略专家。根据用户给出的「文档画像」，判断最佳切分参数。
只输出一个 JSON 对象，字段：
- doc_type: 文档类型（如 technical_markdown / prose / code / faq / table）
- language: zh 或 en
- strategy: 切分策略名（如 markdown_header / fixed_size / semantic）
- chunk_size: 整数，每块目标字符数（中文 300-600，英文技术文档 600-1200）
- chunk_overlap: 整数，块间重叠字符数（通常为 chunk_size 的 10%-20%）
- separators: 字符串数组，递归切分的分隔符（从大到小，如 ["\\n## ","\\n### ","\\n\\n","\\n"," "]）
- prepend_heading_path: 布尔，是否给每块前置所属标题路径作为上下文
- reasoning: 简短中文说明你的判断依据
- suggested_answer_prompt: 一段用于该知识库 RAG 回答的 system prompt（中文）
不要输出 JSON 以外的任何内容。"""


def analyze_chunking(profile: dict) -> dict:
    """让 LLM 根据文档画像产出结构化切分方案。"""
    user = "文档画像：\n" + json.dumps(profile, ensure_ascii=False, indent=2)
    resp = _client().chat.completions.create(
        model=_config["model"],
        messages=[
            {"role": "system", "content": ANALYZE_SYSTEM},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = resp.choices[0].message.content or "{}"
    return json.loads(content)
