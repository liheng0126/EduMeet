"""Provider 工厂：按模型表 provider 路由（deepseek→真实 API，其余→Mock）。

Spec 00/07 约定：路由封装收敛在此层，业务接口不可绕过。
"""
from app.core.response import ERR_FORBIDDEN, EduMeetError
from app.llm.deepseek_provider import DeepSeekProvider
from app.llm.mock_provider import MockProvider
from app.llm.provider import LLMProvider


def get_provider_for(provider: str) -> LLMProvider:
    if provider == "deepseek":
        p = DeepSeekProvider()
        if not p.api_key:
            raise EduMeetError(ERR_FORBIDDEN, "DeepSeek 未配置：请在 backend/.env 填入 DEEPSEEK_API_KEY 后重启后端")
        return p
    return MockProvider()
