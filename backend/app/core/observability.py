"""Langfuse 可观测性封装（Spec 00 §5.3：LLM 追踪走 Langfuse）

设计要点：
- 懒初始化：首个埋点触发；未配置 Keys 时所有埋点自动退化为 no-op，业务零影响；
- 环境变量必须在 import SDK 之前注入（SDK 实例化时读取 os.environ）；
- trace 结构遵循官方最佳实践（https://langfuse.com/docs/observability/best-practices）：
    trace(span, 携带 user_id/session_id/tags/trace_name)
      ├─ retriever   检索步骤（as_type="retriever"）
      └─ generation  LLM 调用（as_type="generation"，含 model/input/output/usage_details）
- 所有上下文管理器跨 SSE yield 安全（span 在生成器关闭时自动结束）。
"""
from __future__ import annotations

import contextlib
import os
from typing import Any

from app.core.config import get_settings

_client: Any | None = None
_init_done = False


def get_langfuse() -> Any | None:
    """返回 Langfuse 客户端；未配置 Keys 时返回 None（调用方按 no-op 处理）。"""
    global _client, _init_done
    if _init_done:
        return _client
    _init_done = True
    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return None
    # 最佳实践：先注入环境变量，再 import SDK，避免 SDK 以空凭据初始化
    os.environ["LANGFUSE_PUBLIC_KEY"] = s.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = s.langfuse_secret_key
    os.environ["LANGFUSE_HOST"] = s.langfuse_host
    try:
        from langfuse import Langfuse

        _client = Langfuse(environment="dev")
    except Exception as exc:  # noqa: BLE001
        print(f"[langfuse] 初始化失败，埋点降级为 no-op：{exc}")
        _client = None
    return _client


def flush() -> None:
    """进程退出前强制刷出缓冲中的观测数据（脚本/长进程关闭时调用）。"""
    if _client is not None:
        with contextlib.suppress(Exception):
            _client.flush()


@contextlib.contextmanager
def trace(
    name: str,
    *,
    as_type: str = "span",
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    trace_name: str | None = None,
    **kwargs: Any,
):
    """创建一个观测节点（span/generation/retriever/agent...），yield 观测对象（未启用时为 None）。

    顶层节点传入 user_id / session_id / trace_name / tags 以写入 trace 属性；
    嵌套节点在同一个 trace 上下文内调用即可自动挂在父节点下。
    """
    lf = get_langfuse()
    if lf is None:
        yield None
        return
    from langfuse import propagate_attributes

    with lf.start_as_current_observation(as_type=as_type, name=name, **kwargs) as obs:
        if user_id is not None or session_id is not None or trace_name is not None or tags:
            with propagate_attributes(
                user_id=user_id, session_id=session_id, tags=tags, trace_name=trace_name
            ):
                yield obs
        else:
            yield obs
