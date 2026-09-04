"""Mock Provider：不调用外部 API，流式输出教育场景示例回答（SSE 冒烟链路用）。"""
import asyncio
from collections.abc import AsyncGenerator

from app.llm.provider import Citation, LLMProvider

_FAQ_CITATIONS = [
    Citation(title="北京市义务教育入学服务平台（官方）", url="https://yjrx.bjedu.cn"),
    Citation(title="教育部：义务教育入学政策文件", url="https://www.moe.gov.cn"),
]

_ARTICLE_TEMPLATE = """# {topic}

> 本文由 EduMeet AI 生成（Mock 模式），发布前请核对政策类信息并补充来源。

## 一、背景

围绕「{topic}」，家长最关心的是政策适用范围、时间节点与材料准备。以下内容为骨架示例，用于验证生成链路。

## 二、核心要点

1. 确认户籍与房产对应的入学片区，关注当年官方发布的入学政策文件；
2. 留意信息采集与材料审核的时间窗口，逾期会影响派位顺序；
3. 政策逐年微调，务必以官方最新版本为准。

## 三、行动清单

- 关注所在区教委官网与官方公众号
- 提前准备户口簿、房产证明等材料
- 有疑问优先咨询学校或区教委，避免依赖非官方渠道
"""


class MockProvider(LLMProvider):
    async def stream_chat(self, model_id: str, messages: list[dict]) -> AsyncGenerator[dict, None]:
        last = messages[-1]["content"] if messages else ""
        answer = (
            f"关于「{last}」：这是 EduMeet Mock 模式的流式回答。\n\n"
            "1. 入学政策类问题请以所在区教委当年发布的官方文件为准；\n"
            "2. 政策存在时效性，注意核对版本与年份；\n"
            "3. 接入真实模型后（LLM_PROVIDER=litellm），本回答将替换为真实模型输出并附来源引用。\n"
        )
        for i in range(0, len(answer), 12):
            await asyncio.sleep(0.03)  # 模拟流式节奏
            yield {"type": "delta", "content": answer[i : i + 12]}
        yield {"type": "citations", "citations": [c.__dict__ for c in _FAQ_CITATIONS]}

    async def generate_article(self, model_id: str, topic: str) -> tuple[str, list[Citation]]:
        await asyncio.sleep(0.5)  # 模拟生成耗时
        return _ARTICLE_TEMPLATE.format(topic=topic), _FAQ_CITATIONS
