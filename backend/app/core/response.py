"""统一响应包与错误码（Spec 03 附录：{code, message, data}）"""
from typing import Any

from fastapi import HTTPException, status

RESPONSE_OK = 0


def ok(data: Any = None, message: str = "ok") -> dict:
    return {"code": RESPONSE_OK, "message": message, "data": data}


class EduMeetError(HTTPException):
    """业务错误：code 为 Spec 03 附录错误码。骨架版 HTTP 状态统一 200，由 code 区分。"""

    def __init__(self, code: int, message: str):
        super().__init__(status_code=status.HTTP_200_OK, detail={"code": code, "message": message})
        self.biz_code = code
        self.biz_message = message


ERR_AUTH = 40101          # 未登录 / token 失效
ERR_USER_EXISTS = 40102   # 用户名已存在
ERR_NOT_FOUND = 40400     # 资源不存在
ERR_FORBIDDEN = 40300     # 无权限（如操作他人文章）
