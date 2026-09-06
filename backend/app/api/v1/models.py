"""模型列表（Spec 03/07：用户自选模型接口）"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ok
from app.db.session import get_db
from app.models.llm_model import LLMModel

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models(db: AsyncSession = Depends(get_db)) -> dict:
    rows = (
        await db.scalars(
            select(LLMModel)
            .where(LLMModel.enabled.is_(True))
            .order_by(LLMModel.sort_order.asc(), LLMModel.id.asc())
        )
    ).all()
    return ok([
        {
            "id": m.id,
            "name": m.name,
            "vendor": m.vendor,
            "free": m.free,
            "description": m.description,
        }
        for m in rows
    ])
