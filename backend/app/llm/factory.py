"""Provider 工厂：按模型注册表路由（deepseek-chat→真实 API，其余→Mock）。

Spec 00/07 约定：路由封装收敛在此层，业务接口不可绕过。
"""
from app.core.response import ERR_FORBIDDEN, EduMeetError
from app.llm.deepseek_provider import DeepSeekProvider
from app.llm.mock_provider import MockProvider
from app.llm.provider import LLMProvider
from app.llm.registry import get_model


def get_provider_for(model_id: str) -> LLMProvider:
    model = get_model(model_id)
    if model is None:
        raise EduMeetError(40400, "模型不存在")
    if model.provider == "deepseek":
        p = DeepSeekProvider()
        if not p.api_key:
            raise EduMeetError(ERR_FORBIDDEN, "DeepSeek 未配置：请在 backend/.env 填入 DEEPSEEK_API_KEY 后重启后端")
        return p
    return MockProvider()
