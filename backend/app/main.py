"""FastAPI 入口（Spec 00 §5.1）"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.observability import flush as lf_flush
from app.core.response import RESPONSE_OK
from app.db.session import init_db
from app.api.v1 import articles, auth, models, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    lf_flush()  # 退出前刷出 Langfuse 缓冲的 trace


app = FastAPI(title=get_settings().app_name, version="0.1.0-skeleton", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一响应包：业务错误转为 {code, message}（Spec 00 §5.2）
@app.exception_handler(Exception)
async def unified_error_handler(request: Request, exc: Exception):
    biz = getattr(exc, "biz_code", None)
    if biz is not None:
        return JSONResponse({"code": biz, "message": getattr(exc, "biz_message", "error"), "data": None})
    raise exc


app.include_router(auth.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(articles.router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health() -> dict:
    return {"code": RESPONSE_OK, "message": "ok", "data": {"status": "up"}}
