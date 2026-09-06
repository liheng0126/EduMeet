"""应用配置（Spec 00 §5.3：环境变量 + .env，密钥不入库）"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "EduMeet API"
    # 仅连接 EduMeet 业务库。Langfuse 通过独立 SDK/HOST 上报，不使用此连接。
    database_url: str = "sqlite+aiosqlite:///./edumeet.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720
    llm_provider: str = "mock"  # mock | litellm
    litellm_base_url: str = "http://localhost:4000"
    litellm_api_key: str = ""
    # DeepSeek 真实接入（密钥不入库，放 backend/.env）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    # Langfuse 可观测性（LLM 追踪，密钥不入库）
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    langfuse_base_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
