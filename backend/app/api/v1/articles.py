"""文章与生成（Spec 03 §6 骨架版；红线 4：author_id 强制绑定当前账号）"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.observability import trace
from app.core.response import ERR_FORBIDDEN, ERR_NOT_FOUND, EduMeetError, ok
from app.db.session import get_db
from app.llm.factory import get_provider_for
from app.llm.registry import get_model
from app.models.article import Article, GenerationTask
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
) -> dict:
    """AI 生成文章草稿。骨架为同步 Mock；M1 迭代替换为 Celery + LangGraph 流水线（Spec 04）。"""
    if get_model(body.model_id) is None:
        raise EduMeetError(ERR_NOT_FOUND, "模型不存在")
    task = GenerationTask(user_id=user.id, topic=body.topic, status="running", model_id=body.model_id)
    db.add(task)
    await db.commit()

    provider = get_provider_for(body.model_id)
    with trace(
        "generate-article", as_type="span", trace_name="generate-article",
        user_id=str(user.id), tags=["article", body.model_id],
        input={"topic": body.topic, "model": body.model_id},
    ) as root:
        with trace("llm-article", as_type="generation", model=body.model_id,
                   input={"topic": body.topic},
                   metadata={"provider": type(provider).__name__}) as gen:
            content_md, _citations = await provider.generate_article(body.model_id, body.topic)
            if gen is not None:
                gen.update(output=content_md)
        # 红线 4：生成内容强制绑定当前账号为作者
        art = Article(author_id=user.id, title=body.topic, source="ai_generated",
                      content_md=content_md, model_id=body.model_id)
        db.add(art)
        await db.flush()
        task.status, task.article_id = "succeeded", art.id
        await db.commit()
        if root is not None:
            root.update(output={"article_id": art.id, "chars": len(content_md)})
    return ok({"task_id": task.id, "article": ArticleOut.model_validate(art).model_dump()})


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
