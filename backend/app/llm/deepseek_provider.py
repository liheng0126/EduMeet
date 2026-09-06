"""DeepSeek 真实接入（OpenAI 兼容协议，Spec 07）

- stream_chat：SSE 流式（chat/completions stream=true），逐 delta 转发
- stream_generate_article：SSE 流式生成文章 Markdown
"""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Optional

import httpx

from app.core.config import get_settings
from app.core.response import ERR_FORBIDDEN, EduMeetError
from app.llm.provider import Citation, LLMProvider


def _friendly(e: httpx.HTTPStatusError, body: str = "") -> EduMeetError:
    """把 DeepSeek 官方错误码映射为用户可读的业务提示（body 可选，流式路径不读 body）。"""
    code = e.response.status_code
    if code == 402:
        return EduMeetError(ERR_FORBIDDEN, "DeepSeek 账户余额不足：请到 platform.deepseek.com 充值后重试")
    if code == 401:
        return EduMeetError(ERR_FORBIDDEN, "DeepSeek API Key 无效：请检查 backend/.env 中的 DEEPSEEK_API_KEY")
    if code == 429:
        return EduMeetError(ERR_FORBIDDEN, "DeepSeek 请求限流：请稍后重试")
    return EduMeetError(ERR_FORBIDDEN, f"DeepSeek 调用失败（HTTP {code}）：{body[:200]}")

SYSTEM_PROMPT = (
    "你是 EduMeet 中小学生教育智能助手，服务对象为家长、学生与教师，"
    "主题覆盖入学政策、学习资料、家庭教育与教学经验。"
    "回答要求：①政策类问题必须提醒以当地教委/教育部当年官方文件为准，不得编造具体政策数字；"
    "②结构清晰，适当使用列表与小标题；③中文回答，语气专业友好。"
)

_ARTICLE_PROMPT = (
    "请以教育内容平台作者身份，围绕主题「{topic}」写一篇文章（Markdown 格式）："
    "包含 2~3 个小节标题、要点列表与行动建议；政策类内容须注明「请以官方最新文件为准」；800 字以内。"
)


class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        s = get_settings()
        self.api_key = api_key or s.deepseek_api_key
        self.base_url = s.deepseek_base_url.rstrip("/")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def _stream_completion(self, messages: list[dict]) -> AsyncGenerator[dict, None]:
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},  # 供 Langfuse usage/成本统计
        }
        usage = None
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", json=payload, headers=self._headers()
            ) as resp:
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise _friendly(e)  # 流式响应未 read，不访问 body
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if chunk.get("usage"):
                        u = chunk["usage"]
                        usage = {"input": u.get("prompt_tokens"), "output": u.get("completion_tokens")}
                        continue
                    delta = chunk["choices"][0].get("delta", {}).get("content")
                    if delta:
                        yield {"type": "delta", "content": delta}
        if usage:
            yield {"type": "usage", **usage}

    async def stream_chat(self, model_id: str, messages: list[dict]) -> AsyncGenerator[dict, None]:
        async for chunk in self._stream_completion(
            [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
        ):
            yield chunk
        # DeepSeek 无检索引用；citation 能力随 M2 混合检索接入（Spec 06）
        yield {"type": "citations", "citations": []}

    async def stream_generate_article(self, model_id: str, topic: str) -> AsyncGenerator[dict, None]:
        async for chunk in self._stream_completion(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _ARTICLE_PROMPT.format(topic=topic)},
            ]
        ):
            yield chunk
        yield {"type": "citations", "citations": []}

    async def generate_article(self, model_id: str, topic: str) -> tuple[str, list[Citation]]:
        content: list[str] = []
        async for chunk in self.stream_generate_article(model_id, topic):
            if chunk["type"] == "delta":
                content.append(chunk["content"])
        return "".join(content), []
