"""模型注册表（Spec 07 P0 清单）

provider 字段决定真实/模拟路由：deepseek-chat 走 DeepSeek 真实 API，其余暂为 mock。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    vendor: str
    free: bool
    description: str
    provider: str = "mock"  # mock | deepseek


DEFAULT_MODEL_REGISTRY: list[ModelInfo] = [
    ModelInfo("doubao-lite", "豆包 Lite", "字节火山", True, "免费模型（每日额度内），沙箱用户唯一可用", provider="mock"),
    ModelInfo("doubao-pro", "豆包 Pro", "字节火山", False, "P0 文本主力，教育内容质量佳", provider="mock"),
    ModelInfo("deepseek-chat", "DeepSeek V3", "DeepSeek", False, "P0 文本，真实接入已启用", provider="deepseek"),
    ModelInfo("qwen3", "通义千问 Qwen3", "阿里", False, "P0 文本，中文政策语料友好", provider="mock"),
]
