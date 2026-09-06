"""EduMeet 业务库会话；不参与 Langfuse 观测数据的存储。"""
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.llm.registry import DEFAULT_MODEL_REGISTRY
from app.models import article, conversation, llm_model, user  # noqa: F401 确保模型注册
from app.models.llm_model import LLMModel

engine = create_async_engine(get_settings().database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def close_db() -> None:
    """释放 EduMeet 业务库连接池。"""
    await engine.dispose()


async def init_db() -> None:
    """创建缺失表并初始化模型目录；MySQL 也可直接执行 db/schema_mysql.sql。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_default_models()


async def seed_default_models() -> None:
    """初始化内置模型目录；已有记录不覆盖，便于本地调整 provider/enabled。"""
    async with SessionLocal() as session:
        existing_ids = set((await session.scalars(select(LLMModel.id))).all())
        for idx, model in enumerate(DEFAULT_MODEL_REGISTRY, start=1):
            if model.id in existing_ids:
                continue
            session.add(
                LLMModel(
                    id=model.id,
                    name=model.name,
                    vendor=model.vendor,
                    free=model.free,
                    description=model.description,
                    provider=model.provider,
                    enabled=True,
                    sort_order=idx,
                )
            )
        await session.commit()
