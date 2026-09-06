"""文章与 SSE 流式生成（红线 4：author_id 强制绑定当前账号）。"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.observability import trace
from app.core.response import ERR_FORBIDDEN, ERR_NOT_FOUND, EduMeetError, ok
from app.db.session import get_db
from app.llm.factory import get_provider_for
from app.models.article import Article, GenerationTask
from app.models.llm_model import LLMModel
from app.models.user import User
from app.schemas.article import ArticleOut, GenerateIn

router = APIRouter(prefix="/articles", tags=["articles"])


async def _owned_article(db: AsyncSession, user: User, article_id: int) -> Article:
    art = await db.get(Article, article_id)
    if art is None:
        raise EduMeetError(ERR_NOT_FOUND, "文章不存在")
    if art.author_id != user.id:
        raise EduMeetError(ERR_FORBIDDEN, "仅作者本人可操作该文章")
    return art


@router.post("/generate")
async def generate(
    body: GenerateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """流式生成文章，完成后持久化草稿并通过 done 事件返回文章数据。"""
    model = await db.get(LLMModel, body.model_id)
    if model is None or not model.enabled:
        raise EduMeetError(ERR_NOT_FOUND, "模型不存在")
    task = GenerationTask(user_id=user.id, topic=body.topic, status="running", model_id=body.model_id)
    db.add(task)
    await db.commit()

    provider = get_provider_for(model.provider)

    async def event_gen():
        content_parts: list[str] = []
        usage = None
        yield f"event: task_progress\ndata: {json.dumps({'stage': 'planning', 'detail': '正在规划文章结构…'}, ensure_ascii=False)}\n\n"
        with trace(
            "generate-article", as_type="span", trace_name="generate-article",
            user_id=str(user.id), tags=["article", body.model_id],
            input={"topic": body.topic, "model": body.model_id},
        ) as root:
            try:
                with trace(
                    "llm-article", as_type="generation", model=body.model_id,
                    input={"topic": body.topic},
                    metadata={"provider": model.provider, "provider_class": type(provider).__name__},
                ) as gen:
                    yield f"event: task_progress\ndata: {json.dumps({'stage': 'generating', 'detail': '正在生成文章内容…'}, ensure_ascii=False)}\n\n"
                    async for chunk in provider.stream_generate_article(body.model_id, body.topic):
                        if chunk["type"] == "delta":
                            content_parts.append(chunk["content"])
                            yield f"event: message_delta\ndata: {json.dumps({'content': chunk['content']}, ensure_ascii=False)}\n\n"
                        elif chunk["type"] == "usage":
                            usage = {"input": chunk.get("input"), "output": chunk.get("output")}
                    content_md = "".join(content_parts)
                    if gen is not None:
                        gen.update(output=content_md, usage_details=usage)

                # 生成全部完成后再落库，避免保存不完整草稿。
                art = Article(
                    author_id=user.id, title=body.topic, source="ai_generated",
                    content_md=content_md, model_id=body.model_id,
                )
                db.add(art)
                await db.flush()
                task.status, task.article_id = "succeeded", art.id
                await db.commit()
                article_data = ArticleOut.model_validate(art).model_dump()
                if root is not None:
                    root.update(output={"article_id": art.id, "chars": len(content_md)})
                done = {"stage": "done", "task_id": task.id, "article": article_data}
                yield f"event: task_progress\ndata: {json.dumps(done, ensure_ascii=False, default=str)}\n\n"
            except Exception as exc:  # noqa: BLE001
                task.status = "failed"
                await db.commit()
                message = getattr(exc, "biz_message", None) or str(exc)
                if root is not None:
                    root.update(level="ERROR", status_message=message)
                yield f"event: error\ndata: {json.dumps({'message': message}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/mine")
async def my_articles(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    rows = await db.scalars(
        select(Article).where(Article.author_id == user.id).order_by(Article.id.desc())
    )
    return ok([ArticleOut.model_validate(a).model_dump() for a in rows])


@router.get("/{article_id}")
async def get_article(
    article_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    art = await _owned_article(db, user, article_id)
    return ok(ArticleOut.model_validate(art).model_dump())


@router.post("/{article_id}/publish")
async def publish(
    article_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    art = await _owned_article(db, user, article_id)
    if art.status == "published":
        return ok(ArticleOut.model_validate(art).model_dump(), message="已发布")
    # 红线 1：发布必过安全审核（骨架为机审 stub，M1 迭代接安全审查节点）
    art.status = "published"
    art.published_at = datetime.now(timezone.utc)
    await db.commit()
    return ok(ArticleOut.model_validate(art).model_dump())
