"""认证与密码（骨架用 PBKDF2 + 盐，M1 正式版可替换 passlib/bcrypt）"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"pbkdf2${salt}${digest}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        _, salt, digest = hashed.split("$")
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return secrets.compare_digest(calc, digest)


def create_access_token(user_id: int) -> str:
    s = get_settings()
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> int | None:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
        return int(payload["sub"])
    except jwt.PyJWTError:
        return None
