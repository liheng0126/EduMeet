"""模型列表（Spec 03/07：用户自选模型的骨架版注册表接口）"""
from fastapi import APIRouter

from app.core.response import ok
from app.llm.registry import MODEL_REGISTRY

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models() -> dict:
    return ok([
        {
            "id": m.id,
            "name": m.name,
            "vendor": m.vendor,
            "free": m.free,
            "description": m.description,
        }
        for m in MODEL_REGISTRY
    ])
