"""文章与生成任务（Spec 02 §2.3 骨架子集）

全局红线 4：author_id NOT NULL —— 不允许存在无主内容。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | published
    source: Mapped[str] = mapped_column(String(16), default="ai_generated")  # ai_generated | manual
    content_md: Mapped[str] = mapped_column(Text, default="")
    model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GenerationTask(Base):
    __tablename__ = "generation_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    topic: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="succeeded")  # 骨架同步完成；正式版 pending/running/failed
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# 红线校验辅助索引：按作者查文章
Index("ix_articles_author_status", Article.author_id, Article.status)
