from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ConversationOut(BaseModel):
    id: int
    title: str

    class Config:
        from_attributes = True


class ChatStreamIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    model_id: str = "doubao-lite"


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: Optional[list] = None
    model_id: Optional[str] = None

    class Config:
        from_attributes = True
