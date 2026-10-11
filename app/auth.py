import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User


security = HTTPBearer(auto_error=False)

# Простое хранилище токенов в памяти (достаточно для учебного сервиса ДЗ1).
_tokens: dict[str, tuple[int, datetime]] = {}


def hash_password(password: str) -> str:
    salt = settings.secret_key.encode()
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000).hex()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def create_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    _tokens[token] = (user_id, datetime.utcnow() + timedelta(hours=12))
    return token


def revoke_token(token: str) -> None:
    _tokens.pop(token, None)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authorization required")

    token = credentials.credentials
    payload = _tokens.get(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    user_id, expires_at = payload
    if expires_at < datetime.utcnow():
        _tokens.pop(token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token expired")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user
