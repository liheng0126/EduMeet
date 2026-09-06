"""LLM Provider 抽象：骨架 mock；正式版接 LiteLLM 网关（Spec 07 §5），接口保持不变。"""
from collections.abc import AsyncGenerator
from dataclasses import dataclass


@dataclass
class Citation:
    title: str
    url: str


class LLMProvider:
    async def stream_chat(self, model_id: str, messages: list[dict]) -> AsyncGenerator[dict, None]:
        """yield {"type": "delta", "content": str} 与 {"type": "citations", "citations": [...]}"""
        raise NotImplementedError
        yield  # pragma: no cover

    async def generate_article(self, model_id: str, topic: str) -> tuple[str, list[Citation]]:
        """返回 (markdown, citations)"""
        raise NotImplementedError  # pragma: no cover

    async def stream_generate_article(self, model_id: str, topic: str) -> AsyncGenerator[dict, None]:
        """流式生成文章，事件结构与 stream_chat 一致。"""
        raise NotImplementedError
        yield  # pragma: no cover
