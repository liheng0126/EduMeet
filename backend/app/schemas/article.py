from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GenerateIn(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    model_id: str = "doubao-pro"


class ArticleOut(BaseModel):
    id: int
    author_id: int
    title: str
    status: str
    source: str
    content_md: str
    model_id: Optional[str] = None

    class Config:
        from_attributes = True


class ArticleBrief(BaseModel):
    id: int
    title: str
    status: str
    source: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True
