"""会话与 SSE 流式问答（Spec 03 §4 / §5.3 事件契约骨架版）

SSE 事件名固定：message_delta | task_progress | error，data 为 JSON 字符串。
"""
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.observability import trace
from app.core.response import ERR_NOT_FOUND, EduMeetError, ok
from app.db.session import get_db
from app.llm.factory import get_provider_for
from app.models.conversation import Conversation, Message
from app.models.llm_model import LLMModel
from app.models.user import User
from app.schemas.chat import ChatStreamIn, ConversationOut, MessageOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _owned_session(db: AsyncSession, user: User, session_id: int) -> Conversation:
    conv = await db.get(Conversation, session_id)
    if conv is None or conv.user_id != user.id:
        raise EduMeetError(ERR_NOT_FOUND, "会话不存在")
    return conv


@router.get("")
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    rows = await db.scalars(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.id.desc())
    )
    return ok([ConversationOut.model_validate(c).model_dump() for c in rows])


@router.post("")
async def create_session(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    conv = Conversation(user_id=user.id, title="新会话")
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ok(ConversationOut.model_validate(conv).model_dump())


@router.get("/{session_id}/messages")
async def list_messages(
    session_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    conv = await _owned_session(db, user, session_id)
    msgs = (await db.scalars(select(Message).where(Message.session_id == conv.id).order_by(Message.id))).all()
    return ok([MessageOut.model_validate(m).model_dump() for m in msgs])


@router.post("/{session_id}/chat/stream")
async def chat_stream(
    session_id: int,
    body: ChatStreamIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    conv = await _owned_session(db, user, session_id)
    model = await db.get(LLMModel, body.model_id)
    if model is None or not model.enabled:
        raise EduMeetError(ERR_NOT_FOUND, "模型不存在")
    provider = get_provider_for(model.provider)

    user_msg = Message(session_id=conv.id, role="user", content=body.content)
    db.add(user_msg)
    await db.commit()

    async def event_gen():
        full, citations, usage = [], None, None
        # Langfuse 根 trace：一次对话 = 一条 trace，关联用户与会话（Sessions 视图可看完整多轮）
        with trace(
            "chat-response", as_type="span", trace_name="chat-response",
            user_id=str(user.id), session_id=str(conv.id), tags=["chat", body.model_id],
            input={"message": body.content, "model": body.model_id},
        ) as root:
            try:
                yield f"event: task_progress\ndata: {json.dumps({'stage': 'retrieving', 'detail': '检索教育内容库…'}, ensure_ascii=False)}\n\n"
                with trace("retrieve-context", as_type="retriever",
                           input={"query": body.content, "top_k": 6}) as retr:
                    history = (
                        await db.scalars(
                            select(Message).where(Message.session_id == conv.id).order_by(Message.id.desc()).limit(6)
                        )
                    ).all()
                    if retr is not None:
                        retr.update(output={"history_messages": len(history)})
                llm_messages = [{"role": m.role, "content": m.content} for m in reversed(history)]
                with trace("llm-chat", as_type="generation", model=body.model_id,
                           input=llm_messages,
                           metadata={"provider": model.provider, "provider_class": type(provider).__name__}) as gen:
                    async for chunk in provider.stream_chat(body.model_id, llm_messages):
                        if chunk["type"] == "delta":
                            full.append(chunk["content"])
                            yield f"event: message_delta\ndata: {json.dumps({'content': chunk['content']}, ensure_ascii=False)}\n\n"
                        elif chunk["type"] == "usage":
                            usage = {"input": chunk.get("input"), "output": chunk.get("output")}
                        elif chunk["type"] == "citations":
                            citations = chunk["citations"]
                            yield f"event: task_progress\ndata: {json.dumps({'stage': 'citations', 'detail': '附加来源引用'}, ensure_ascii=False)}\n\n"
                    if gen is not None:
                        gen.update(output="".join(full), usage_details=usage)
                # 持久化 assistant 消息
                async with db.begin_nested():
                    pass
                assistant = Message(
                    session_id=conv.id, role="assistant", content="".join(full),
                    citations=citations, model_id=body.model_id,
                )
                db.add(assistant)
                if conv.title == "新会话":
                    conv.title = body.content[:24]
                await db.commit()
                if root is not None:
                    root.update(output={"answer": "".join(full), "citations": citations})
                yield f"event: task_progress\ndata: {json.dumps({'stage': 'done', 'message_id': assistant.id, 'title': conv.title}, ensure_ascii=False)}\n\n"
            except Exception as exc:  # noqa: BLE001
                msg = getattr(exc, "biz_message", None) or str(exc)
                if root is not None:
                    root.update(level="ERROR", status_message=msg, output={"answer": "".join(full)})
                yield f"event: error\ndata: {json.dumps({'message': msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
