"""Platform kill-switch / maintenance mode service backed by PostgreSQL."""

from __future__ import annotations

import html
import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, Optional

from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.models.platform_control import DEFAULT_MAINTENANCE_MESSAGE, PlatformControl

logger = logging.getLogger(__name__)

SINGLETON_ID = 1
_CACHE_TTL_SECONDS = 2.0

MAINTENANCE_HEADERS: dict[str, str] = {
    "Retry-After": "60",
    "Cache-Control": "no-store",
}


class PlatformStoppedError(Exception):
    """Raised when a non-admin request/login is rejected because the platform is stopped."""

    def __init__(self, maintenance_message: str, stopped_at: Optional[str] = None):
        self.maintenance_message = (maintenance_message or "").strip() or DEFAULT_MAINTENANCE_MESSAGE
        self.stopped_at = stopped_at
        super().__init__(self.maintenance_message)


def build_maintenance_json_payload(
    maintenance_message: str,
    stopped_at: Optional[str] = None,
) -> dict[str, Any]:
    """Build the canonical HTTP 503 maintenance JSON payload."""
    clean_msg = (maintenance_message or "").strip() or DEFAULT_MAINTENANCE_MESSAGE
    return {
        "detail": clean_msg,
        "error": "platform_stopped",
        "maintenance_mode": True,
        "is_active": False,
        "stopped_at": stopped_at,
    }

_cache_lock = threading.Lock()
# Maps bind_id -> (expires_at_monotonic, status_dict)
_status_cache: dict[int, tuple[float, dict[str, Any]]] = {}
_ensured_binds: set[int] = set()


def _get_bind_key(db: Session) -> tuple[int, bool]:
    """Return (bind_id, is_sqlite) for cache partitioning."""
    bind = db.get_bind()
    bind_id = id(bind)
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
    return bind_id, (dialect_name == "sqlite")


def _ensure_table(db: Session, *, force: bool = False) -> None:
    """Idempotently ensure the platform_control table exists on the active bind."""
    bind = db.get_bind()
    bind_id = id(bind)
    if not force and bind_id in _ensured_binds:
        return
    try:
        PlatformControl.__table__.create(bind=bind, checkfirst=True)
        _ensured_binds.add(bind_id)
    except Exception as exc:
        logger.warning(f"[PlatformControl] Could not ensure platform_control table: {exc}")


def _iso_or_none(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _serialize_row(row: Optional[PlatformControl]) -> dict[str, Any]:
    if row is None:
        return {
            "is_active": True,
            "maintenance_mode": False,
            "maintenance_message": DEFAULT_MAINTENANCE_MESSAGE,
            "stopped_at": None,
            "updated_at": None,
            "updated_by": None,
            "updated_by_name": None,
        }
    is_active = bool(row.is_active)
    message = (row.maintenance_message or "").strip() or DEFAULT_MAINTENANCE_MESSAGE
    return {
        "is_active": is_active,
        "maintenance_mode": not is_active,
        "maintenance_message": message,
        "stopped_at": _iso_or_none(row.stopped_at),
        "updated_at": _iso_or_none(row.updated_at),
        "updated_by": row.updated_by,
        "updated_by_name": row.updated_by_name,
    }


def clear_platform_status_cache() -> None:
    """Clear in-memory platform status cache (useful in tests)."""
    with _cache_lock:
        _status_cache.clear()
        _ensured_binds.clear()


def get_platform_status(db: Session, *, bypass_cache: bool = False) -> dict[str, Any]:
    """Return full platform status dict, reading from DB with short TTL caching."""
    bind_id, is_sqlite = _get_bind_key(db)
    ttl = 0.0 if is_sqlite else _CACHE_TTL_SECONDS
    now = time.monotonic()

    if not bypass_cache and ttl > 0:
        with _cache_lock:
            cached = _status_cache.get(bind_id)
            if cached and cached[0] > now:
                return dict(cached[1])

    _ensure_table(db)

    try:
        row = db.query(PlatformControl).filter(PlatformControl.id == SINGLETON_ID).first()
    except (OperationalError, ProgrammingError):
        # Table might have been dropped/recreated; retry once after ensuring table
        try:
            db.rollback()
        except Exception:
            pass
        _ensure_table(db, force=True)
        try:
            row = db.query(PlatformControl).filter(PlatformControl.id == SINGLETON_ID).first()
        except Exception as exc:
            logger.warning(f"[PlatformControl] DB read failed after retry: {exc}")
            with _cache_lock:
                cached = _status_cache.get(bind_id)
                if cached:
                    return dict(cached[1])
            return _serialize_row(None)
    except Exception as exc:
        logger.warning(f"[PlatformControl] Unexpected DB error reading status: {exc}")
        with _cache_lock:
            cached = _status_cache.get(bind_id)
            if cached:
                return dict(cached[1])
        return _serialize_row(None)

    result = _serialize_row(row)
    if ttl > 0:
        with _cache_lock:
            _status_cache[bind_id] = (now + ttl, dict(result))
    return result


def get_public_platform_status(db: Session, *, bypass_cache: bool = False) -> dict[str, Any]:
    """Public-safe status payload (omits internal admin ID/name)."""
    full = get_platform_status(db, bypass_cache=bypass_cache)
    return {
        "is_active": full["is_active"],
        "maintenance_mode": full["maintenance_mode"],
        "maintenance_message": full["maintenance_message"],
        "stopped_at": full["stopped_at"],
        "updated_at": full["updated_at"],
    }


def is_platform_active(db: Session, *, bypass_cache: bool = False) -> bool:
    """Return True if the platform is operational, False if stopped."""
    return bool(get_platform_status(db, bypass_cache=bypass_cache)["is_active"])


def set_platform_status(
    db: Session,
    *,
    is_active: bool,
    maintenance_message: Optional[str] = None,
    admin_id: Optional[int] = None,
    admin_name: Optional[str] = None,
) -> dict[str, Any]:
    """Persist the global platform on/off state and immediately refresh the cache."""
    _ensure_table(db)

    resolved_name = admin_name
    if not resolved_name and admin_id:
        try:
            from app.models.user import User

            admin_user = db.query(User).filter(User.user_id == admin_id).first()
            if admin_user and admin_user.name:
                resolved_name = admin_user.name
        except Exception:
            pass
    if not resolved_name:
        resolved_name = "مدير النظام"

    now_utc = datetime.now(timezone.utc)

    def _apply_update(existing: PlatformControl) -> None:
        was_active = bool(existing.is_active)
        existing.is_active = bool(is_active)
        if maintenance_message is not None:
            cleaned = maintenance_message.strip()
            existing.maintenance_message = cleaned if cleaned else DEFAULT_MAINTENANCE_MESSAGE
        elif not (existing.maintenance_message or "").strip():
            existing.maintenance_message = DEFAULT_MAINTENANCE_MESSAGE

        if is_active:
            existing.stopped_at = None
        elif was_active or existing.stopped_at is None:
            existing.stopped_at = now_utc

        existing.updated_at = now_utc
        existing.updated_by = admin_id
        existing.updated_by_name = resolved_name

    row = db.query(PlatformControl).filter(PlatformControl.id == SINGLETON_ID).first()
    if row is None:
        clean_msg = (maintenance_message or "").strip() or DEFAULT_MAINTENANCE_MESSAGE
        row = PlatformControl(
            id=SINGLETON_ID,
            is_active=bool(is_active),
            maintenance_message=clean_msg,
            stopped_at=None if is_active else now_utc,
            updated_at=now_utc,
            updated_by=admin_id,
            updated_by_name=resolved_name,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            # Concurrent first-write race on singleton id=1: roll back and update the winner's row
            db.rollback()
            row = db.query(PlatformControl).filter(PlatformControl.id == SINGLETON_ID).first()
            if row is None:
                raise
            _apply_update(row)
            db.commit()
    else:
        _apply_update(row)
        db.commit()

    db.refresh(row)

    result = _serialize_row(row)
    bind_id, is_sqlite = _get_bind_key(db)
    with _cache_lock:
        if is_sqlite:
            _status_cache.pop(bind_id, None)
        else:
            _status_cache[bind_id] = (time.monotonic() + _CACHE_TTL_SECONDS, dict(result))

    return result


@contextmanager
def resolve_db_session_for_app(app: Any) -> Generator[Session, None, None]:
    """Open a DB session respecting FastAPI's get_db dependency_overrides (for tests)."""
    overrides = getattr(app, "dependency_overrides", None) or {}
    override_fn = overrides.get(get_db)
    if override_fn is not None:
        gen = override_fn()
        db = next(gen)
        try:
            yield db
        finally:
            try:
                next(gen)
            except StopIteration:
                pass
            except Exception:
                pass
    else:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


def render_maintenance_html(
    maintenance_message: str,
    stopped_at: Optional[str] = None,
) -> str:
    """Render a branded RTL Arabic 503 Maintenance HTML page for browser visitors."""
    safe_msg = html.escape((maintenance_message or DEFAULT_MAINTENANCE_MESSAGE).strip())
    safe_time = html.escape(stopped_at) if stopped_at else ""
    time_block = (
        f'<p class="meta">وقت الإيقاف: <span dir="ltr">{safe_time}</span></p>'
        if safe_time
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>المنصة متوقفة مؤقتاً | مدرسة WE للتكنولوجيا التطبيقية بالسويس</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@500;700;800;900&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Cairo', system-ui, -apple-system, sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      background: radial-gradient(circle at top right, #4A154B 0%, #1e1033 45%, #0f172a 100%);
      color: #f8fafc;
    }}
    .card {{
      width: 100%;
      max-width: 540px;
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(244, 63, 94, 0.35);
      border-radius: 28px;
      padding: 40px 32px;
      text-align: center;
      box-shadow: 0 25px 60px rgba(0, 0, 0, 0.45);
      backdrop-filter: blur(14px);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 16px;
      border-radius: 999px;
      background: rgba(244, 63, 94, 0.16);
      border: 1px solid rgba(244, 63, 94, 0.4);
      color: #fda4af;
      font-size: 13px;
      font-weight: 800;
      margin-bottom: 20px;
    }}
    .dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: #f43f5e;
      animation: pulse 1.5s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(0.85); }}
    }}
    .icon-box {{
      width: 78px;
      height: 78px;
      margin: 0 auto 20px;
      border-radius: 22px;
      background: linear-gradient(135deg, #be123c, #7c3aed);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 34px;
      box-shadow: 0 12px 28px rgba(190, 18, 60, 0.35);
    }}
    h1 {{
      font-size: 24px;
      font-weight: 900;
      margin-bottom: 10px;
      color: #ffffff;
    }}
    .school {{
      font-size: 13px;
      font-weight: 700;
      color: #c4b5fd;
      margin-bottom: 18px;
    }}
    .msg {{
      background: rgba(30, 41, 59, 0.7);
      border: 1px solid rgba(148, 163, 184, 0.2);
      border-radius: 16px;
      padding: 18px 20px;
      font-size: 15px;
      line-height: 1.8;
      color: #e2e8f0;
      margin-bottom: 20px;
      white-space: pre-line;
    }}
    .meta {{
      font-size: 12px;
      color: #94a3b8;
      margin-bottom: 20px;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: center;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 12px 24px;
      border-radius: 14px;
      font-family: inherit;
      font-size: 14px;
      font-weight: 800;
      cursor: pointer;
      text-decoration: none;
      border: none;
      transition: transform 0.15s ease, opacity 0.15s ease;
    }}
    .btn:hover {{ opacity: 0.92; transform: translateY(-1px); }}
    .btn-primary {{
      background: linear-gradient(135deg, #7c3aed, #4f46e5);
      color: #ffffff;
    }}
    .btn-admin {{
      background: rgba(148, 163, 184, 0.14);
      color: #cbd5e1;
      border: 1px solid rgba(148, 163, 184, 0.25);
    }}
  </style>
</head>
<body>
  <main class="card">
    <div class="badge">
      <span class="dot"></span>
      <span>المنصة متوقفة مؤقتاً (503)</span>
    </div>
    <div class="icon-box" aria-hidden="true">⏻</div>
    <h1>عذراً، المنصة متوقفة حالياً</h1>
    <p class="school">مدرسة WE للتكنولوجيا التطبيقية بالسويس</p>
    <div class="msg">{safe_msg}</div>
    {time_block}
    <div class="actions">
      <button class="btn btn-primary" onclick="window.location.reload()">🔄 إعادة المحاولة</button>
      <a class="btn btn-admin" href="/admin">🔐 دخول لوحة الإدارة</a>
    </div>
  </main>
</body>
</html>"""
