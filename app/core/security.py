import time
import threading
import uuid
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

bearer_scheme = HTTPBearer()

_REVOKED_JTIS: dict[str, float] = {}
_REVOKED_LOCK = threading.Lock()


def _prune_revoked(now_ts: float) -> None:
    expired = [jti for jti, exp in _REVOKED_JTIS.items() if exp and exp < now_ts]
    for jti in expired:
        _REVOKED_JTIS.pop(jti, None)


def revoke_token(token: str, db=None) -> None:
    """Revoke a JWT token by its JTI (or token digest fallback) until expiry."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},
        )
    except Exception:
        return
    jti = payload.get("jti") or token[-32:]
    exp = float(payload.get("exp") or (time.time() + 86400))
    with _REVOKED_LOCK:
        _prune_revoked(time.time())
        _REVOKED_JTIS[str(jti)] = exp


def is_token_revoked(payload: dict) -> bool:
    jti = payload.get("jti")
    if not jti:
        return False
    now_ts = time.time()
    with _REVOKED_LOCK:
        _prune_revoked(now_ts)
        exp = _REVOKED_JTIS.get(str(jti))
        return exp is not None and exp >= now_ts


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
    to_encode.setdefault("jti", uuid.uuid4().hex)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_reset_token(user_id: int) -> str:
    return create_access_token(
        {"sub": str(user_id), "purpose": "reset"},
        expires_minutes=settings.RESET_TOKEN_EXPIRE_MINUTES,
    )


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    if is_token_revoked(payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ── Dependency: get current user_id ───────────────────────────────────────────

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> int:
    payload = decode_token(credentials.credentials)
    if payload.get("purpose") == "reset":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token cannot be used for standard API authentication",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return int(user_id)


def get_current_user_id_ws(token: str) -> int:
    payload = decode_token(token)
    if payload.get("purpose") == "reset":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token cannot be used for WebSocket authentication",
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return int(user_id)


def require_admin_role(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> int:
    payload = decode_token(credentials.credentials)
    if payload.get("purpose") == "reset":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token cannot be used for API authentication",
        )
    user_id = payload.get("sub")
    user_type = payload.get("type")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token missing subject")
    if user_type != "ADM":
        raise HTTPException(status_code=403, detail="Administrator privileges required")
    return int(user_id)
