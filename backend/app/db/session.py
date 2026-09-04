"""异步会话管理：生产 PostgreSQL(asyncpg) / 开发 SQLite(aiosqlite) 同一套代码"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.models import article, conversation, user  # noqa: F401 确保模型注册

engine = create_async_engine(get_settings().database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """骨架版建表；Spec 00 §5.2 约定正式版走 Alembic，M1 迭代时引入 alembic 基线。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
