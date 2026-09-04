"""认证与用户（Spec 03 §2 契约骨架版）"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import ERR_USER_EXISTS, EduMeetError, ok
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db)) -> dict:
    exists = await db.scalar(select(User).where(User.username == body.username))
    if exists:
        raise EduMeetError(ERR_USER_EXISTS, "用户名已存在")
    user = User(
        username=body.username,
        nickname=body.nickname or body.username,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return ok(TokenOut(token=create_access_token(user.id), user=UserOut.model_validate(user)).model_dump())


@router.post("/login")
async def login(body: LoginIn, db: AsyncSession = Depends(get_db)) -> dict:
    user = await db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise EduMeetError(ERR_USER_EXISTS, "用户名或密码错误")
    return ok(TokenOut(token=create_access_token(user.id), user=UserOut.model_validate(user)).model_dump())


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> dict:
    return ok(UserOut.model_validate(user).model_dump())
