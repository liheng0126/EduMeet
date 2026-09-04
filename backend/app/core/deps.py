"""依赖注入：当前登录用户（全局红线 4：生成/创作内容必须可解析到 author_id）"""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ERR_AUTH, EduMeetError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if cred is None:
        raise EduMeetError(ERR_AUTH, "未登录或 token 缺失")
    user_id = decode_access_token(cred.credentials)
    if user_id is None:
        raise EduMeetError(ERR_AUTH, "token 无效或已过期")
    user = await db.get(User, user_id)
    if user is None:
        raise EduMeetError(ERR_AUTH, "用户不存在")
    return user
