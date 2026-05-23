from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import uuid

from app.core.config import settings
from app.db.database import get_db

bearer_scheme = HTTPBearer()


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── Tokens ────────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode["exp"] = expire
    to_encode["jti"] = str(uuid.uuid4())
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_reset_token(user_id: int) -> str:
    return create_access_token(
        {"sub": str(user_id), "purpose": "reset"},
        expires_minutes=settings.RESET_TOKEN_EXPIRE_MINUTES,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# ── Blacklist helpers ─────────────────────────────────────────────────────────

def _is_blacklisted(db: Session, jti: str) -> bool:
    from app.models.user import BlacklistedToken
    return db.query(BlacklistedToken).filter(BlacklistedToken.jti == jti).first() is not None


def blacklist_token(db: Session, payload: dict) -> None:
    from app.models.user import BlacklistedToken
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    db.add(BlacklistedToken(jti=jti, expires_at=expires_at))
    db.commit()


# ── Dependency: get current user_id from Bearer token ────────────────────────

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> int:
    payload = decode_token(credentials.credentials)
    jti = payload.get("jti")
    if jti and _is_blacklisted(db, jti):
        raise HTTPException(status_code=401, detail="Token has been revoked")
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return int(user_id)


def get_current_user_id_ws(token: str) -> int:
    """For WebSocket endpoints that pass token as query param."""
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return int(user_id)
