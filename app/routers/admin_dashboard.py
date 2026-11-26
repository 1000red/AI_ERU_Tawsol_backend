import os
import secrets
from fastapi import APIRouter, Depends, Query, Request, HTTPException, status, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List

from app.core.config import settings
from app.core.security import decode_token
from app.db.database import get_db
from app.schemas.user import (
    UserOut,
    AdminUserCreate,
    AdminUserUpdate,
    AdminPasswordReset,
    TeacherAssignmentUpdate,
)
from app.schemas.material import MaterialOut, MaterialCreate
from app.schemas.platform import PlatformStatusOut, PlatformStatusUpdate
from app.services import user_service as user_svc
from app.services import material_service as mat_svc
from app.services import platform_service as platform_svc

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


def require_admin_access(request: Request, db: Session = Depends(get_db)) -> int:
    """Security guard requiring authenticated Administrator role or admin API key.
    Enforces header-only credentials (rejects URL query parameters) and timing-safe comparisons.
    """
    # 1. Reject credentials in URL query parameters to prevent leakage in proxy/access logs
    if "admin_key" in request.query_params or "token" in request.query_params or "key" in request.query_params:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="إرسال بيانات الاعتماد عبر الرابط محظور أمنياً. يرجى استخدام ترويسة Authorization أو X-Admin-Key.",
        )

    # 2. Check X-Admin-Key header with timing-safe constant-time comparison
    admin_key = request.headers.get("x-admin-key")
    if admin_key:
        dedicated_key = os.getenv("ADMIN_API_KEY", "")
        is_prod = bool(os.getenv("VERCEL") or os.getenv("ENVIRONMENT") == "production")
        fallback_key = (
            settings.SECRET_KEY
            if not is_prod and settings.SECRET_KEY and "change-this" not in settings.SECRET_KEY
            else ""
        )
        valid_key = dedicated_key or fallback_key
        if valid_key and secrets.compare_digest(admin_key, valid_key):
            return 1

    # 3. Check Bearer token from Authorization header or HttpOnly/secure cookie
    token = None
    is_cookie_auth = False
    auth = request.headers.get("authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ")[1]
    elif request.cookies.get("admin_token"):
        token = request.cookies.get("admin_token")
        is_cookie_auth = True

    if token:
        try:
            payload = decode_token(token)
            user_type = payload.get("type")
            user_id = int(payload.get("sub", 0))
            is_adm = False
            if user_type == "ADM":
                is_adm = True
            elif user_id > 0:
                user = user_svc.get_user_by_id(db, user_id)
                if user and user.type_code == "ADM":
                    is_adm = True

            if is_adm:
                # If authenticated via ambient cookie, verify double-submit CSRF token on mutating methods
                if is_cookie_auth and request.method in ("POST", "PUT", "DELETE", "PATCH"):
                    csrf_header = request.headers.get("x-csrf-token")
                    csrf_cookie = request.cookies.get("csrf_token")
                    if not csrf_header or not csrf_cookie or not secrets.compare_digest(csrf_header, csrf_cookie):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="رمز الحماية ضد التزوير (CSRF Token) غير صالح أو مفقود.",
                        )
                return user_id
        except HTTPException:
            raise
        except Exception:
            pass

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="صلاحيات المسؤول مطلوبة لتنفيذ هذا الإجراء. يرجى تسجيل الدخول بحساب مسؤول أولاً.",
    )


def require_super_admin_access(request: Request, db: Session = Depends(get_db)) -> int:
    """Security guard requiring authenticated Root/Super Administrator role.
    Strictly required for permanent destructive operations and platform kill-switch.
    """
    admin_id = require_admin_access(request, db)
    # Root API key access is always super admin
    admin_key = request.headers.get("x-admin-key")
    if admin_key:
        return admin_id

    try:
        user = user_svc.get_user_by_id(db, admin_id)
        if user and user.type_code == "ADM":
            return admin_id
    except Exception:
        pass

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="صلاحية المشرف الأعلى (SUPER_ADMIN) مطلوبة لتنفيذ هذا الإجراء.",
    )


def get_optional_admin_access(request: Request, db: Session = Depends(get_db)) -> Optional[int]:
    """Optional admin authentication: returns admin_id if valid admin credentials are provided.
    If credentials of a non-admin user (e.g. STU or DR) are provided, raises 403 Forbidden to maintain strict RBAC.
    If unauthenticated (no credentials provided), returns None allowing safe read-only capacity telemetry.
    """
    token = None
    auth = request.headers.get("authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ")[1]
    elif request.cookies.get("admin_token"):
        token = request.cookies.get("admin_token")

    if token or request.headers.get("x-admin-key"):
        return require_admin_access(request, db)

    return None


def _get_client_ip(request: Request) -> Optional[str]:
    ip = request.headers.get("x-forwarded-for")
    if ip:
        return ip.split(",")[0].strip()
    return request.client.host if request.client else None


# ── API Endpoints ─────────────────────────────────────────────────────────────

@router.get("/api/platform/status", response_model=PlatformStatusOut)
def get_platform_status_admin(
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Get current global platform operational state (on/off kill-switch)."""
    return platform_svc.get_platform_status(db, bypass_cache=True)


@router.put("/api/platform/status", response_model=PlatformStatusOut)
@router.post("/api/platform/status", response_model=PlatformStatusOut)
async def update_platform_status_admin(
    data: PlatformStatusUpdate,
    request: Request,
    admin_id: int = Depends(require_super_admin_access),
    db: Session = Depends(get_db),
):
    """Stop or resume the entire platform globally from the Admin Panel."""
    result = platform_svc.set_platform_status(
        db,
        is_active=data.is_active,
        maintenance_message=data.maintenance_message,
        admin_id=admin_id,
    )
    from app.services.admin_audit_service import admin_audit_service
    admin_user = None
    try:
        admin_user = user_svc.get_user_by_id(db, admin_id)
    except Exception:
        pass

    admin_audit_service.log_action(
        db,
        action="PLATFORM_START" if data.is_active else "PLATFORM_STOP",
        admin_id=admin_id,
        admin_email=admin_user.email if admin_user else None,
        admin_name=admin_user.name if admin_user else None,
        target_resource="platform:killswitch",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        details=f"is_active={data.is_active}, maintenance_message={data.maintenance_message}",
    )
    if not data.is_active:
        try:
            from app.services.chat_service import ws_manager
            from app.websockets import announcement_manager
            await ws_manager.disconnect_all(maintenance_message=result["maintenance_message"])
            await announcement_manager.disconnect_all(maintenance_message=result["maintenance_message"])
        except Exception:
            pass
    return result


@router.get("/api/stats")
def get_stats(
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Return dashboard analytics & metrics."""
    return user_svc.get_dashboard_stats(db)


@router.get("/api/users", response_model=list[UserOut])
def get_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """List users with search, role filter, and pagination."""
    return user_svc.list_all_users(db, search, role, department, limit, offset)


@router.post("/api/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    data: AdminUserCreate,
    request: Request,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Create a new user (student, doctor, admin) with encrypted password."""
    new_user = user_svc.create_user_admin(db, data)
    from app.services.admin_audit_service import admin_audit_service
    admin_audit_service.log_action(
        db,
        action="USER_CREATE",
        admin_id=admin_id,
        target_resource=f"user:{new_user.user_id}",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        details=f"Created user {new_user.email} (type={new_user.type_code}, name={new_user.name})",
    )
    return new_user


@router.put("/api/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: AdminUserUpdate,
    request: Request,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Update user information."""
    updated = user_svc.update_user_admin(db, user_id, data)
    from app.services.admin_audit_service import admin_audit_service
    admin_audit_service.log_action(
        db,
        action="USER_UPDATE",
        admin_id=admin_id,
        target_resource=f"user:{user_id}",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        details=f"Updated profile for user {user_id}",
    )
    return updated


@router.put("/api/users/{user_id}/courses", response_model=UserOut)
def update_teacher_courses(
    user_id: int,
    data: TeacherAssignmentUpdate,
    request: Request,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Assign/update teacher's department and scoped courses."""
    user = user_svc.get_user_by_id(db, user_id)
    if data.department is not None:
        dept = data.department.strip()
        user.department = dept if dept else None

    from app.models.material import MaterialTeacher
    db.query(MaterialTeacher).filter(MaterialTeacher.user_id == user_id).delete()
    for cid in data.assigned_courses:
        cid_clean = str(cid).strip()
        if cid_clean:
            db.add(MaterialTeacher(material_id=cid_clean, user_id=user_id))
    db.commit()
    db.refresh(user)

    rows = db.query(MaterialTeacher.material_id).filter(MaterialTeacher.user_id == user_id).all()
    user.assigned_courses = [r[0] for r in rows]

    from app.services.admin_audit_service import admin_audit_service
    admin_audit_service.log_action(
        db,
        action="ASSIGN_COURSES",
        admin_id=admin_id,
        target_resource=f"user:{user_id}",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        details=f"Assigned courses {data.assigned_courses} to user {user_id}",
    )
    return user


@router.post("/api/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    data: AdminPasswordReset,
    request: Request,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Reset any user's password directly."""
    user_svc.reset_password_admin(db, user_id, data.new_password)
    from app.services.admin_audit_service import admin_audit_service
    admin_audit_service.log_action(
        db,
        action="PASSWORD_RESET",
        admin_id=admin_id,
        target_resource=f"user:{user_id}",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        details=f"Admin reset password for user {user_id}",
    )
    return {"message": "Password reset successfully", "user_id": user_id}


@router.delete("/api/users/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Delete a user."""
    user_svc.delete_user_admin(db, user_id)
    from app.services.admin_audit_service import admin_audit_service
    admin_audit_service.log_action(
        db,
        action="USER_DELETE",
        admin_id=admin_id,
        target_resource=f"user:{user_id}",
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        details=f"Deleted user {user_id}",
    )
    return {"message": "User deleted successfully", "user_id": user_id}


@router.get("/api/audit")
def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Query recent administrative security audit logs."""
    from app.services.admin_audit_service import admin_audit_service
    return admin_audit_service.get_recent_logs(db, limit=limit, action=action)


@router.get("/api/courses", response_model=list[MaterialOut])
def get_courses(
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """List all courses with assigned teachers."""
    return mat_svc.get_all_materials(db)


@router.post("/api/courses", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
def create_course(
    data: MaterialCreate,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Add a new course / material."""
    return mat_svc.create_material(db, data)


@router.delete("/api/courses/{material_id}")
def delete_course(
    material_id: str,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Delete a course."""
    mat_svc.delete_material(db, material_id)
    return {"message": f"Course '{material_id}' deleted successfully"}


# ── Chat Monitoring Endpoints ────────────────────────────────────────────────

@router.get("/api/chats/stats")
def get_chats_stats(
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Analytics and metrics for chat system."""
    from app.models.chat import ChatHistory
    from app.models.user import User
    from sqlalchemy import func
    from datetime import datetime, date

    today_start = datetime.combine(date.today(), datetime.min.time())
    total_messages = db.query(func.count(ChatHistory.chat_id)).scalar() or 0
    messages_today = db.query(func.count(ChatHistory.chat_id)).filter(ChatHistory.sent_at >= today_start).scalar() or 0

    types_query = (
        db.query(ChatHistory.content_type, func.count(ChatHistory.chat_id))
        .group_by(ChatHistory.content_type)
        .all()
    )
    content_types = {t or "text": count for t, count in types_query}

    p_min = func.least(ChatHistory.sender_id, ChatHistory.receiver_id)
    p_max = func.greatest(ChatHistory.sender_id, ChatHistory.receiver_id)
    total_threads = (
        db.query(p_min, p_max)
        .distinct()
        .count()
    )

    top_senders = (
        db.query(
            User.user_id,
            User.name,
            User.email,
            User.type_code,
            func.count(ChatHistory.chat_id).label("sent_count")
        )
        .join(ChatHistory, ChatHistory.sender_id == User.user_id)
        .group_by(User.user_id, User.name, User.email, User.type_code)
        .order_by(func.count(ChatHistory.chat_id).desc())
        .limit(6)
        .all()
    )

    return {
        "total_messages": total_messages,
        "messages_today": messages_today,
        "total_threads": total_threads,
        "content_types": content_types,
        "top_senders": [
            {
                "user_id": s.user_id,
                "name": s.name,
                "email": s.email,
                "role": s.type_code,
                "sent_count": s.sent_count,
            }
            for s in top_senders
        ],
    }


@router.get("/api/chats/conversations")
def get_conversations(
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """List conversation threads between any two users."""
    from app.models.chat import ChatHistory
    from app.models.user import User
    from sqlalchemy import func, desc

    p_min = func.least(ChatHistory.sender_id, ChatHistory.receiver_id).label("u1")
    p_max = func.greatest(ChatHistory.sender_id, ChatHistory.receiver_id).label("u2")

    threads_query = (
        db.query(
            p_min,
            p_max,
            func.count(ChatHistory.chat_id).label("msg_count"),
            func.max(ChatHistory.sent_at).label("last_sent_at"),
            func.max(ChatHistory.chat_id).label("last_chat_id"),
        )
        .group_by(p_min, p_max)
        .order_by(desc("last_sent_at"))
    )

    raw_threads = threads_query.all()
    if not raw_threads:
        return {"total": 0, "conversations": []}

    all_uids = set()
    for t in raw_threads:
        all_uids.add(t.u1)
        all_uids.add(t.u2)

    users_map = {
        u.user_id: {
            "user_id": u.user_id,
            "name": u.name,
            "email": u.email,
            "role": u.type_code,
            "code": getattr(u, "uni_code", None) or getattr(u, "student_code", None) or getattr(u, "code", None),
            "department": getattr(u, "department", None),
        }
        for u in db.query(User).filter(User.user_id.in_(all_uids)).all()
    }

    last_ids = [t.last_chat_id for t in raw_threads if t.last_chat_id]
    msgs_map = {
        m.chat_id: {
            "message": m.message,
            "content_type": m.content_type,
            "sender_id": m.sender_id,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        }
        for m in db.query(ChatHistory).filter(ChatHistory.chat_id.in_(last_ids)).all()
    }

    results = []
    for t in raw_threads:
        u1_info = users_map.get(t.u1, {"user_id": t.u1, "name": f"User #{t.u1}", "role": "STU"})
        u2_info = users_map.get(t.u2, {"user_id": t.u2, "name": f"User #{t.u2}", "role": "STU"})
        last_m = msgs_map.get(t.last_chat_id, {})

        if search:
            s_low = search.strip().lower()
            match1 = s_low in u1_info["name"].lower() or s_low in (u1_info.get("email") or "").lower()
            match2 = s_low in u2_info["name"].lower() or s_low in (u2_info.get("email") or "").lower()
            if not (match1 or match2):
                continue

        results.append({
            "user1": u1_info,
            "user2": u2_info,
            "total_messages": t.msg_count,
            "last_message": last_m.get("message") or f"[{last_m.get('content_type', 'ملف')}]",
            "last_message_type": last_m.get("content_type", "text"),
            "last_message_sender_id": last_m.get("sender_id"),
            "last_sent_at": t.last_sent_at.isoformat() if t.last_sent_at else None,
        })

    paginated = results[offset: offset + limit]
    return {
        "total": len(results),
        "conversations": paginated,
    }


@router.get("/api/chats/thread")
def get_chat_thread(
    user1_id: int,
    user2_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Retrieve full chat transcript between two specific users."""
    from app.models.chat import ChatHistory
    from app.models.user import User
    from sqlalchemy import or_, and_, asc

    condition = or_(
        and_(ChatHistory.sender_id == user1_id, ChatHistory.receiver_id == user2_id),
        and_(ChatHistory.sender_id == user2_id, ChatHistory.receiver_id == user1_id),
    )

    total = db.query(ChatHistory).filter(condition).count()
    msgs = (
        db.query(ChatHistory)
        .filter(condition)
        .order_by(asc(ChatHistory.sent_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    u1 = db.query(User).filter(User.user_id == user1_id).first()
    u2 = db.query(User).filter(User.user_id == user2_id).first()

    return {
        "user1": {
            "id": u1.user_id if u1 else user1_id,
            "name": u1.name if u1 else f"User #{user1_id}",
            "role": u1.type_code if u1 else "STU",
            "department": getattr(u1, "department", None),
        },
        "user2": {
            "id": u2.user_id if u2 else user2_id,
            "name": u2.name if u2 else f"User #{user2_id}",
            "role": u2.type_code if u2 else "STU",
            "department": getattr(u2, "department", None),
        },
        "total": total,
        "messages": [
            {
                "chat_id": m.chat_id,
                "sender_id": m.sender_id,
                "receiver_id": m.receiver_id,
                "message": m.message,
                "content_type": m.content_type,
                "file_url": m.file_url,
                "file_name": m.file_name,
                "file_size_bytes": m.file_size_bytes,
                "voice_duration_seconds": m.voice_duration_seconds,
                "status": m.status,
                "is_deleted": m.is_deleted,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            }
            for m in msgs
        ],
    }


@router.get("/api/chats/recent")
def get_recent_messages(
    content_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Live global stream of recent chat messages across all users."""
    from app.models.chat import ChatHistory
    from app.models.user import User

    q = db.query(ChatHistory).order_by(ChatHistory.sent_at.desc())
    if content_type:
        q = q.filter(ChatHistory.content_type == content_type)

    raw_msgs = q.limit(limit).all()
    uids = set()
    for m in raw_msgs:
        uids.add(m.sender_id)
        uids.add(m.receiver_id)

    users_map = {
        u.user_id: {"name": u.name, "role": u.type_code, "email": u.email}
        for u in db.query(User).filter(User.user_id.in_(uids)).all()
    }

    return [
        {
            "chat_id": m.chat_id,
            "sender": users_map.get(m.sender_id, {"name": f"User #{m.sender_id}", "role": "STU"}),
            "receiver": users_map.get(m.receiver_id, {"name": f"User #{m.receiver_id}", "role": "STU"}),
            "message": m.message,
            "content_type": m.content_type,
            "file_url": m.file_url,
            "file_name": m.file_name,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        }
        for m in raw_msgs
    ]


# ── AI Quiz Monitoring Endpoints ─────────────────────────────────────────────

@router.get("/api/quizzes/stats")
def get_quizzes_stats(
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Comprehensive AI Quiz usage statistics, real student exam metrics, and Gemini API counters."""
    from app.models.quiz_log import QuizLog, QuizStudentAttempt
    from app.models.user import User
    from app.models.material import Material
    from sqlalchemy import func
    from datetime import datetime, date

    try:
        bind = db.get_bind()
        QuizLog.__table__.create(bind=bind, checkfirst=True)
        QuizStudentAttempt.__table__.create(bind=bind, checkfirst=True)
    except Exception:
        pass

    total_quizzes = db.query(func.count(QuizLog.id)).scalar() or 0
    total_questions = db.query(func.sum(QuizLog.num_questions)).scalar() or 0
    logged_attempts = db.query(func.sum(QuizLog.attempts_count)).scalar() or 0
    recorded_attempts = db.query(func.count(QuizStudentAttempt.id)).scalar() or 0
    total_attempts = max(int(logged_attempts or 0), int(recorded_attempts or 0))

    # Quizzes created today
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_quizzes = (
        db.query(func.count(QuizLog.id))
        .filter(QuizLog.created_at >= today_start)
        .scalar()
        or 0
    )

    # Count student quizzes/attempts vs teacher-generated quizzes
    student_authored_quizzes = (
        db.query(func.count(QuizLog.id))
        .join(User, QuizLog.user_id == User.user_id)
        .filter(User.type_code == "STU")
        .scalar()
        or 0
    )
    students_quizzes = max(int(student_authored_quizzes), int(recorded_attempts))
    teachers_quizzes = (
        db.query(func.count(QuizLog.id))
        .join(User, QuizLog.user_id == User.user_id)
        .filter(User.type_code.in_(["DR", "TA", "ADM"]))
        .scalar()
        or 0
    )

    diff_query = (
        db.query(QuizLog.difficulty, func.count(QuizLog.id))
        .group_by(QuizLog.difficulty)
        .all()
    )
    diff_breakdown = {d or "medium": count for d, count in diff_query}

    # Material name lookup
    material_names = {}
    try:
        material_names = {m.material_id: m.name for m in db.query(Material).all()}
    except Exception:
        pass

    course_query = (
        db.query(QuizLog.course_id, func.count(QuizLog.id))
        .filter(QuizLog.course_id != None)
        .group_by(QuizLog.course_id)
        .order_by(func.count(QuizLog.id).desc())
        .limit(8)
        .all()
    )
    course_breakdown = [
        {
            "course_id": c[0],
            "course_name": material_names.get(c[0], c[0]),
            "count": c[1],
        }
        for c in course_query
    ]

    # Real student quiz performance summary (prefer QuizStudentAttempt, fallback to QuizLog.score)
    attempt_avg_raw = db.query(func.avg(QuizStudentAttempt.score)).scalar()
    if attempt_avg_raw is not None:
        avg_score = round(float(attempt_avg_raw), 1)
    else:
        avg_score_raw = (
            db.query(func.avg(QuizLog.score))
            .filter(QuizLog.score != None)
            .scalar()
        )
        avg_score = round(float(avg_score_raw), 1) if avg_score_raw is not None else 0.0

    top_users_query = (
        db.query(
            User.user_id,
            User.name,
            User.type_code,
            func.count(QuizLog.id).label("quiz_count"),
        )
        .join(QuizLog, QuizLog.user_id == User.user_id)
        .group_by(User.user_id, User.name, User.type_code)
        .order_by(func.count(QuizLog.id).desc())
        .limit(5)
        .all()
    )

    # ── Calculate Gemini Free-Tier Quota & Token Savings ─────────────────────
    from app.services.quiz_service.cache import quiz_cache
    from app.core.config import settings

    cache_stats = quiz_cache.stats
    estimated_tokens_used = total_quizzes * 1400
    estimated_tokens_saved = cache_stats["estimated_tokens_saved"] + (total_quizzes * 3600)

    free_tier_status = {
        "rate_limit_rpm": 15,
        "daily_quota_rpd": 1500,
        "today_api_calls": today_quizzes,
        "remaining_daily_calls": max(0, 1500 - today_quizzes),
        "estimated_tokens_used": estimated_tokens_used,
        "estimated_tokens_saved": estimated_tokens_saved,
        "cache_hits": cache_stats["hits"],
        "cache_hit_rate_pct": cache_stats["hit_rate_pct"],
        "protection_active": True,
        "active_model": getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash-lite"),
    }

    return {
        "total_quizzes": total_quizzes,
        "total_questions": total_questions,
        "total_attempts": total_attempts,
        "today_quizzes": today_quizzes,
        "students_quizzes_count": students_quizzes,
        "teachers_quizzes_count": teachers_quizzes,
        "average_score": avg_score,
        "gemini_model": getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash-lite"),
        "free_tier_status": free_tier_status,
        "difficulty_breakdown": diff_breakdown,
        "courses_breakdown": course_breakdown,
        "top_users": [
            {
                "user_id": u.user_id,
                "name": u.name,
                "role": u.type_code,
                "quiz_count": u.quiz_count,
            }
            for u in top_users_query
        ],
    }


@router.get("/api/quizzes/students-analysis")
def get_students_quiz_analysis(
    course_id: Optional[str] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """
    Dedicated analytics for students' quizzes combining BOTH QuizStudentAttempt
    (student exam submissions) and student-authored QuizLog records.
    """
    from app.models.quiz_log import QuizLog, QuizStudentAttempt
    from app.models.user import User
    from app.models.material import Material
    from collections import defaultdict

    material_names = {}
    try:
        material_names = {m.material_id: m.name for m in db.query(Material).all()}
    except Exception:
        pass

    # Preload QuizLog lookup by id and session_id
    all_logs = db.query(QuizLog).all()
    logs_by_id = {q.id: q for q in all_logs}
    logs_by_session = {q.session_id: q for q in all_logs if q.session_id}

    # Fetch all student users
    students_map = {
        u.user_id: u
        for u in db.query(User).filter(User.type_code == "STU").all()
    }

    # Aggregate per-student records from QuizStudentAttempt + student-owned QuizLog
    per_student = defaultdict(lambda: {
        "scores": [],
        "sessions": set(),
        "courses": set(),
        "total_attempts": 0,
        "last_active": None,
    })
    course_buckets = defaultdict(lambda: {"scores": [], "students": set(), "attempts": 0})
    recorded_student_sessions = set()

    # 1. Real student exam attempts (QuizStudentAttempt)
    attempts = db.query(QuizStudentAttempt).all()
    for att in attempts:
        stu = students_map.get(att.student_id)
        if not stu:
            continue
        linked_log = (
            logs_by_id.get(att.quiz_log_id)
            if att.quiz_log_id
            else logs_by_session.get(att.session_id)
        )
        c_id = (linked_log.course_id if linked_log and linked_log.course_id else "General")

        if course_id and c_id != course_id:
            continue
        if department and (stu.department or "عام") != department:
            continue

        bucket = per_student[stu.user_id]
        if att.score is not None:
            sc_val = float(att.score)
            bucket["scores"].append(sc_val)
            course_buckets[c_id]["scores"].append(sc_val)
        bucket["sessions"].add(att.session_id or f"att-{att.id}")
        bucket["courses"].add(c_id)
        bucket["total_attempts"] += 1
        if att.created_at and (bucket["last_active"] is None or att.created_at > bucket["last_active"]):
            bucket["last_active"] = att.created_at

        course_buckets[c_id]["students"].add(stu.user_id)
        course_buckets[c_id]["attempts"] += 1
        if att.session_id:
            recorded_student_sessions.add((stu.user_id, att.session_id))

    # 2. Also include QuizLog records authored directly by a student (avoiding duplicates)
    for log in all_logs:
        if not log.user_id or log.user_id not in students_map:
            continue
        if log.session_id and (log.user_id, log.session_id) in recorded_student_sessions:
            continue
        stu = students_map[log.user_id]
        c_id = log.course_id or "General"
        if course_id and c_id != course_id:
            continue
        if department and (stu.department or "عام") != department:
            continue

        bucket = per_student[stu.user_id]
        if log.score is not None:
            sc_val = float(log.score)
            bucket["scores"].append(sc_val)
            course_buckets[c_id]["scores"].append(sc_val)
        bucket["sessions"].add(log.session_id or f"log-{log.id}")
        bucket["courses"].add(c_id)
        bucket["total_attempts"] += max(1, int(log.attempts_count or 1))
        if log.created_at and (bucket["last_active"] is None or log.created_at > bucket["last_active"]):
            bucket["last_active"] = log.created_at

        course_buckets[c_id]["students"].add(stu.user_id)
        course_buckets[c_id]["attempts"] += 1

    # 3. Build filtered student performance list
    s_low = search.strip().lower() if search else ""
    students_list = []
    all_scores = []
    total_student_quizzes = 0
    excellent_count = 0
    good_count = 0
    pass_count = 0
    fail_count = 0

    for uid, b in per_student.items():
        stu = students_map[uid]
        if s_low:
            if not (
                s_low in (stu.name or "").lower()
                or s_low in (stu.email or "").lower()
                or s_low in (stu.uni_code or "").lower()
            ):
                continue

        scores = b["scores"]
        avg_sc = round(sum(scores) / len(scores), 1) if scores else None
        max_sc = round(max(scores), 1) if scores else None
        min_sc = round(min(scores), 1) if scores else None
        all_scores.extend(scores)
        total_student_quizzes += len(b["sessions"])

        if avg_sc is not None:
            if avg_sc >= 85:
                status_label = "متميز (ممتاز)"
                excellent_count += 1
            elif avg_sc >= 70:
                status_label = "جيد جداً"
                good_count += 1
            elif avg_sc >= 50:
                status_label = "ناجح"
                pass_count += 1
            else:
                status_label = "يحتاج لمتابعة"
                fail_count += 1
        else:
            status_label = "لم يختبر"

        students_list.append({
            "student_id": stu.user_id,
            "uni_code": stu.uni_code,
            "name": stu.name,
            "email": stu.email,
            "department": stu.department or "عام",
            "level": stu.level,
            "quizzes_count": len(b["sessions"]),
            "avg_score": avg_sc,
            "highest_score": max_sc,
            "lowest_score": min_sc,
            "total_attempts": b["total_attempts"],
            "courses": sorted(b["courses"]),
            "last_active": b["last_active"].isoformat() if b["last_active"] else None,
            "status": status_label,
        })

    # Sort by avg_score desc (then quizzes_count desc)
    students_list.sort(
        key=lambda x: (x["avg_score"] if x["avg_score"] is not None else -1, x["quizzes_count"]),
        reverse=True,
    )

    overall_avg = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0
    passed_evals = sum(1 for s in all_scores if s >= 50.0)
    failed_evals = sum(1 for s in all_scores if s < 50.0)
    pass_rate = round((passed_evals / len(all_scores)) * 100.0, 1) if all_scores else 0.0

    # Per-course performance breakdown for charts
    course_performance = []
    for c_id, cb in sorted(course_buckets.items()):
        c_scores = cb["scores"]
        c_avg = round(sum(c_scores) / len(c_scores), 1) if c_scores else 0.0
        c_pass = round((sum(1 for s in c_scores if s >= 50.0) / len(c_scores)) * 100.0, 1) if c_scores else 0.0
        course_performance.append({
            "course_id": c_id,
            "course_name": material_names.get(c_id, c_id),
            "students_count": len(cb["students"]),
            "attempts_count": cb["attempts"],
            "avg_score": c_avg,
            "pass_rate": c_pass,
        })

    return {
        "summary": {
            "total_students_active": len(students_list),
            "total_student_quizzes": total_student_quizzes,
            "overall_avg_score": overall_avg,
            "pass_rate": pass_rate,
            "passed_quizzes_count": passed_evals,
            "failed_quizzes_count": failed_evals,
            "total_evaluations": len(all_scores),
            "excellent_count": excellent_count,
            "needs_support_count": fail_count,
        },
        "score_distribution": {
            "excellent_85_100": excellent_count,
            "good_70_84": good_count,
            "pass_50_69": pass_count,
            "fail_below_50": fail_count,
        },
        "course_performance": course_performance,
        "students": students_list,
    }


@router.get("/api/quizzes/students/{student_id}")
def get_single_student_quizzes(
    student_id: int,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Detailed quiz history and real exam attempts for a specific student."""
    from app.models.quiz_log import QuizLog, QuizStudentAttempt
    from app.models.user import User

    student = db.query(User).filter(User.user_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    logs = (
        db.query(QuizLog)
        .filter(QuizLog.user_id == student_id)
        .order_by(QuizLog.created_at.desc())
        .all()
    )

    attempts = []
    try:
        attempts = (
            db.query(QuizStudentAttempt)
            .filter(QuizStudentAttempt.student_id == student_id)
            .order_by(QuizStudentAttempt.created_at.desc())
            .all()
        )
    except Exception:
        pass

    # Resolve linked QuizLogs for attempts so topic/course/difficulty are always populated
    linked_ids = {a.quiz_log_id for a in attempts if a.quiz_log_id}
    linked_sessions = {a.session_id for a in attempts if a.session_id}
    linked_logs_by_id = {}
    linked_logs_by_session = {}
    if linked_ids or linked_sessions:
        from sqlalchemy import or_
        conds = []
        if linked_ids:
            conds.append(QuizLog.id.in_(linked_ids))
        if linked_sessions:
            conds.append(QuizLog.session_id.in_(linked_sessions))
        for ql in db.query(QuizLog).filter(or_(*conds)).all():
            linked_logs_by_id[ql.id] = ql
            if ql.session_id:
                linked_logs_by_session[ql.session_id] = ql

    enriched_attempts = []
    merged_quizzes = []
    seen_sessions = set()

    for a in attempts:
        ql = linked_logs_by_id.get(a.quiz_log_id) or linked_logs_by_session.get(a.session_id)
        item = {
            "id": ql.id if ql else a.id,
            "quiz_log_id": ql.id if ql else a.quiz_log_id,
            "attempt_id": a.id,
            "session_id": a.session_id,
            "topic": (ql.topic if ql and ql.topic else "اختبار تفاعلي"),
            "course_id": (ql.course_id if ql and ql.course_id else "General"),
            "difficulty": (ql.difficulty if ql and ql.difficulty else "medium"),
            "num_questions": a.total_questions or (ql.num_questions if ql else 5),
            "correct_count": a.correct_count,
            "total_questions": a.total_questions,
            "score": round(float(a.score), 1) if a.score is not None else None,
            "attempts_count": 1,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        enriched_attempts.append(item)
        merged_quizzes.append(item)
        if a.session_id:
            seen_sessions.add(a.session_id)

    for q in logs:
        if q.session_id and q.session_id in seen_sessions:
            continue
        merged_quizzes.append({
            "id": q.id,
            "quiz_log_id": q.id,
            "attempt_id": None,
            "session_id": q.session_id,
            "topic": q.topic or "اختبار تفاعلي",
            "course_id": q.course_id or "General",
            "difficulty": q.difficulty,
            "num_questions": q.num_questions,
            "correct_count": None,
            "total_questions": q.num_questions,
            "score": round(float(q.score), 1) if q.score is not None else None,
            "attempts_count": q.attempts_count,
            "created_at": q.created_at.isoformat() if q.created_at else None,
        })

    return {
        "student": {
            "id": student.user_id,
            "uni_code": student.uni_code,
            "name": student.name,
            "email": student.email,
            "department": student.department or "عام",
            "level": student.level,
            "role": student.type_code,
        },
        "quizzes": merged_quizzes,
        "attempts": enriched_attempts,
    }



@router.get("/api/quizzes/logs")
def get_quiz_logs(
    search: Optional[str] = None,
    course_id: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """List generated quiz logs with author, course, topic, and difficulty."""
    from app.models.quiz_log import QuizLog
    from app.models.user import User

    try:
        QuizLog.__table__.create(bind=db.get_bind(), checkfirst=True)
    except Exception:
        pass

    q = db.query(QuizLog, User).outerjoin(User, QuizLog.user_id == User.user_id)

    if course_id:
        q = q.filter(QuizLog.course_id == course_id)
    if difficulty:
        q = q.filter(QuizLog.difficulty == difficulty)
    if search:
        s = f"%{search.strip()}%"
        q = q.filter((QuizLog.topic.ilike(s)) | (User.name.ilike(s)) | (QuizLog.session_id.ilike(s)))

    total = q.count()
    rows = q.order_by(QuizLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "quizzes": [
            {
                "id": log.id,
                "session_id": log.session_id,
                "topic": log.topic or "اختبار تفاعلي",
                "course_id": log.course_id or "General",
                "file_id": log.file_id,
                "difficulty": log.difficulty,
                "num_questions": log.num_questions,
                "score": log.score,
                "attempts_count": log.attempts_count,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "author": {
                    "id": user.user_id,
                    "name": user.name,
                    "role": user.type_code,
                    "email": user.email,
                } if user else None,
            }
            for log, user in rows
        ],
    }


@router.get("/api/quizzes/logs/{quiz_id}")
def get_quiz_details(
    quiz_id: int,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Inspect full questions, choices, answers, and explanations of a specific quiz."""
    from app.models.quiz_log import QuizLog
    from app.models.user import User
    import json

    row = db.query(QuizLog).filter(QuizLog.id == quiz_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Quiz log not found")

    author = db.query(User).filter(User.user_id == row.user_id).first() if row.user_id else None

    questions = []
    if row.questions_json:
        try:
            questions = json.loads(row.questions_json)
        except Exception:
            questions = []

    return {
        "id": row.id,
        "session_id": row.session_id,
        "topic": row.topic,
        "course_id": row.course_id,
        "file_id": row.file_id,
        "difficulty": row.difficulty,
        "num_questions": row.num_questions,
        "score": row.score,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "author": {
            "name": author.name if author else "غير مسجل",
            "role": author.type_code if author else "STU",
            "email": author.email if author else "",
        },
        "questions": questions,
    }


# ── User Detailed Activity Monitoring ────────────────────────────────────────

@router.get("/api/users/{user_id}/activity")
def get_user_activity(
    user_id: int,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Detailed activity breakdown for a specific user (chats, quizzes, attempts, files, attendance)."""
    from app.models.chat import ChatHistory
    from app.models.quiz_log import QuizLog, QuizStudentAttempt
    from app.models.content import MaterialFile
    from app.models.attendance import AttendanceRecord
    from sqlalchemy import func

    user = user_svc.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    messages_sent = db.query(func.count(ChatHistory.chat_id)).filter(ChatHistory.sender_id == user_id).scalar() or 0
    messages_received = db.query(func.count(ChatHistory.chat_id)).filter(ChatHistory.receiver_id == user_id).scalar() or 0

    quizzes_count = 0
    quizzes_avg_score = None
    try:
        authored_count = db.query(func.count(QuizLog.id)).filter(QuizLog.user_id == user_id).scalar() or 0
        attempts_count = db.query(func.count(QuizStudentAttempt.id)).filter(QuizStudentAttempt.student_id == user_id).scalar() or 0
        quizzes_count = max(int(authored_count), int(attempts_count))

        att_avg = db.query(func.avg(QuizStudentAttempt.score)).filter(QuizStudentAttempt.student_id == user_id).scalar()
        if att_avg is not None:
            quizzes_avg_score = round(float(att_avg), 1)
        else:
            avg_raw = db.query(func.avg(QuizLog.score)).filter(QuizLog.user_id == user_id, QuizLog.score != None).scalar()
            if avg_raw is not None:
                quizzes_avg_score = round(float(avg_raw), 1)
    except Exception:
        pass

    materials_uploaded = db.query(func.count(MaterialFile.file_id)).filter(MaterialFile.author_id == user_id).scalar() or 0
    attendance_records = db.query(func.count(AttendanceRecord.record_id)).filter(AttendanceRecord.student_id == user_id).scalar() or 0

    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.type_code,
        "department": getattr(user, "department", None),
        "level": getattr(user, "level", None),
        "student_code": getattr(user, "uni_code", None),
        "last_seen": user.last_seen.isoformat() if getattr(user, "last_seen", None) else None,
        "activity": {
            "messages_sent": messages_sent,
            "messages_received": messages_received,
            "quizzes_generated": quizzes_count,
            "quizzes_avg_score": quizzes_avg_score,
            "materials_uploaded": materials_uploaded,
            "attendance_records": attendance_records,
        },
    }


# ── Platform Analytics & Content Usage ("etc") ───────────────────────────────

@router.get("/api/overview")
def get_admin_overview(
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Unified command center metrics, per-course analytics, and 14-day daily activity trends."""
    from app.models.user import User
    from app.models.chat import ChatHistory
    from app.models.quiz_log import QuizLog, QuizStudentAttempt
    from app.models.content import MaterialFile
    from app.models.content.announcement import Announcement
    from app.models.content.assignment import Assignment
    from app.models.contact import ContactMessage
    from app.models.material import Material, MaterialStudent
    from app.models.attendance import AttendanceSession, AttendanceRecord
    from sqlalchemy import func, distinct
    from datetime import datetime, date, timedelta, timezone
    from collections import defaultdict

    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    trend_start_date = today - timedelta(days=13)
    trend_start_dt = datetime.combine(trend_start_date, datetime.min.time())

    # 1. Users & Demographics
    total_users = db.query(func.count(User.user_id)).scalar() or 0
    students_count = db.query(func.count(User.user_id)).filter(User.type_code == "STU").scalar() or 0
    teachers_count = db.query(func.count(User.user_id)).filter(User.type_code.in_(("DR", "TA"))).scalar() or 0
    admins_count = db.query(func.count(User.user_id)).filter(User.type_code == "ADM").scalar() or 0
    active_last_7d = 0
    departments_breakdown = {}
    levels_breakdown = {}
    try:
        active_last_7d = db.query(func.count(User.user_id)).filter(User.last_seen >= seven_days_ago).scalar() or 0
        for dept, cnt in db.query(User.department, func.count(User.user_id)).filter(User.type_code == "STU").group_by(User.department).all():
            departments_breakdown[dept or "عام"] = int(cnt)
        for lvl, cnt in db.query(User.level, func.count(User.user_id)).filter(User.type_code == "STU").group_by(User.level).all():
            levels_breakdown[f"الصف {lvl}" if lvl and lvl > 0 else "غير محدد"] = int(cnt)
    except Exception:
        pass

    # 2. Chats
    total_messages = db.query(func.count(ChatHistory.chat_id)).scalar() or 0
    messages_today = db.query(func.count(ChatHistory.chat_id)).filter(ChatHistory.sent_at >= today_start).scalar() or 0

    # 3. Quizzes & Real Student Attempts
    total_quizzes = 0
    total_questions = 0
    total_quiz_attempts = 0
    quiz_avg_score = 0.0
    quiz_pass_rate = 0.0
    tested_students = 0
    course_quiz_scores = defaultdict(list)
    try:
        bind = db.get_bind()
        try:
            QuizLog.__table__.create(bind=bind, checkfirst=True)
            QuizStudentAttempt.__table__.create(bind=bind, checkfirst=True)
        except Exception:
            pass
        total_quizzes = db.query(func.count(QuizLog.id)).scalar() or 0
        total_questions = db.query(func.sum(QuizLog.num_questions)).scalar() or 0

        logs_map = {q.id: q for q in db.query(QuizLog).all()}
        logs_by_sess = {q.session_id: q for q in logs_map.values() if q.session_id}
        all_attempts = db.query(QuizStudentAttempt).all()
        total_quiz_attempts = len(all_attempts)
        tested_students = len({a.student_id for a in all_attempts})
        att_scores = [float(a.score) for a in all_attempts if a.score is not None]
        if att_scores:
            quiz_avg_score = round(sum(att_scores) / len(att_scores), 1)
            quiz_pass_rate = round((sum(1 for s in att_scores if s >= 50.0) / len(att_scores)) * 100.0, 1)
        for a in all_attempts:
            ql = logs_map.get(a.quiz_log_id) or logs_by_sess.get(a.session_id)
            if ql and ql.course_id and a.score is not None:
                course_quiz_scores[ql.course_id].append(float(a.score))
    except Exception:
        pass

    # 4. Materials, Announcements, Assignments, Support
    total_files = db.query(func.count(MaterialFile.file_id)).scalar() or 0
    total_bytes = db.query(func.sum(MaterialFile.file_size)).scalar() or 0
    size_mb = round(total_bytes / (1024 * 1024), 2) if total_bytes else 0

    announcements_count = 0
    assignments_count = 0
    support_messages_count = 0
    try:
        announcements_count = db.query(func.count(Announcement.announcement_id)).scalar() or 0
        assignments_count = db.query(func.count(Assignment.assignment_id)).scalar() or 0
        support_messages_count = db.query(func.count(ContactMessage.id)).scalar() or 0
    except Exception:
        pass

    # 5. Attendance
    total_sessions = db.query(func.count(AttendanceSession.session_id)).scalar() or 0
    active_sessions = db.query(func.count(AttendanceSession.session_id)).filter(AttendanceSession.is_active == True).scalar() or 0
    total_attendance_records = 0
    present_count = 0
    late_count = 0
    try:
        total_attendance_records = db.query(func.count(AttendanceRecord.record_id)).scalar() or 0
        present_count = db.query(func.count(AttendanceRecord.record_id)).filter(AttendanceRecord.status == "PRESENT").scalar() or 0
        late_count = db.query(func.count(AttendanceRecord.record_id)).filter(AttendanceRecord.status == "LATE").scalar() or 0
    except Exception:
        pass
    avg_attendees_per_session = round(total_attendance_records / total_sessions, 1) if total_sessions > 0 else 0.0

    # 6. Per-Course Breakdown (C1..C8)
    courses_list = []
    try:
        all_courses = db.query(Material).order_by(Material.material_id.asc()).all()
        enroll_map = dict(db.query(MaterialStudent.material_id, func.count(distinct(MaterialStudent.user_id))).group_by(MaterialStudent.material_id).all())
        files_map = dict(db.query(MaterialFile.material_id, func.count(MaterialFile.file_id)).filter(MaterialFile.material_id != None).group_by(MaterialFile.material_id).all())
        sess_map = dict(db.query(AttendanceSession.material_id, func.count(AttendanceSession.session_id)).group_by(AttendanceSession.material_id).all())
        att_map = dict(db.query(AttendanceRecord.material_id, func.count(AttendanceRecord.record_id)).group_by(AttendanceRecord.material_id).all())

        for c in all_courses:
            cid = c.material_id
            c_scores = course_quiz_scores.get(cid, [])
            c_avg = round(sum(c_scores) / len(c_scores), 1) if c_scores else None
            c_pass = round((sum(1 for s in c_scores if s >= 50.0) / len(c_scores)) * 100.0, 1) if c_scores else None
            courses_list.append({
                "course_id": cid,
                "name": c.name,
                "enrolled_students": int(enroll_map.get(cid, 0) or 0),
                "files_count": int(files_map.get(cid, 0) or 0),
                "attendance_sessions": int(sess_map.get(cid, 0) or 0),
                "attendance_records": int(att_map.get(cid, 0) or 0),
                "quiz_attempts": len(c_scores),
                "avg_score": c_avg,
                "pass_rate": c_pass,
            })
    except Exception:
        pass

    # 7. Last 14 Days Daily Activity Trend (Attendance + Quiz Attempts + Chats)
    daily_att = defaultdict(int)
    daily_quiz = defaultdict(int)
    daily_chat = defaultdict(int)
    try:
        for (dt,) in db.query(AttendanceRecord.scanned_at).filter(AttendanceRecord.scanned_at >= trend_start_dt).all():
            if dt:
                daily_att[dt.date().isoformat()] += 1
        for (dt,) in db.query(QuizStudentAttempt.created_at).filter(QuizStudentAttempt.created_at >= trend_start_dt).all():
            if dt:
                daily_quiz[dt.date().isoformat()] += 1
        for (dt,) in db.query(ChatHistory.sent_at).filter(ChatHistory.sent_at >= trend_start_dt).all():
            if dt:
                daily_chat[dt.date().isoformat()] += 1
    except Exception:
        pass

    daily_trend = []
    for offset_days in range(14):
        d = trend_start_date + timedelta(days=offset_days)
        iso = d.isoformat()
        daily_trend.append({
            "date": iso,
            "label": d.strftime("%d/%m"),
            "attendance": daily_att.get(iso, 0),
            "quiz_attempts": daily_quiz.get(iso, 0),
            "chats": daily_chat.get(iso, 0),
        })

    return {
        "users": {
            "total": total_users,
            "students": students_count,
            "teachers": teachers_count,
            "admins": admins_count,
            "active_last_7d": active_last_7d,
            "departments_breakdown": departments_breakdown,
            "levels_breakdown": levels_breakdown,
        },
        "chats": {
            "total_messages": total_messages,
            "messages_today": messages_today,
        },
        "quizzes": {
            "total_quizzes": total_quizzes,
            "total_questions": total_questions,
            "total_attempts": total_quiz_attempts,
            "avg_score": quiz_avg_score,
            "pass_rate": quiz_pass_rate,
            "tested_students": tested_students,
        },
        "materials": {
            "total_files": total_files,
            "size_mb": size_mb,
        },
        "content": {
            "announcements_count": announcements_count,
            "assignments_count": assignments_count,
            "support_messages_count": support_messages_count,
        },
        "courses": {
            "total_courses": len(courses_list),
            "list": courses_list,
        },
        "attendance": {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "total_records": total_attendance_records,
            "present_count": present_count,
            "late_count": late_count,
            "avg_attendees_per_session": avg_attendees_per_session,
        },
        "daily_trend": daily_trend,
        "platform": platform_svc.get_platform_status(db),
    }


@router.get("/api/attendance/sessions")
def get_attendance_sessions_admin(
    course_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """List attendance sessions with attendees count and computed duration for admin monitoring."""
    from app.models.attendance import AttendanceSession, AttendanceRecord
    from app.models.material import Material
    from app.models.user import User
    from sqlalchemy import func

    q = (
        db.query(
            AttendanceSession,
            User.name.label("teacher_name"),
            Material.name.label("course_name"),
            func.count(AttendanceRecord.record_id).label("attendees_count"),
        )
        .outerjoin(User, AttendanceSession.created_by == User.user_id)
        .outerjoin(Material, AttendanceSession.material_id == Material.material_id)
        .outerjoin(AttendanceRecord, AttendanceRecord.session_id == AttendanceSession.session_id)
    )
    if course_id:
        q = q.filter(AttendanceSession.material_id == course_id)

    sessions = (
        q.group_by(AttendanceSession.session_id, User.name, Material.name)
        .order_by(AttendanceSession.created_at.desc())
        .limit(limit)
        .all()
    )

    result = []
    for s in sessions:
        sess = s.AttendanceSession
        duration_mins = 30
        try:
            if sess.expires_at and sess.created_at:
                exp = sess.expires_at.replace(tzinfo=None) if sess.expires_at.tzinfo else sess.expires_at
                crt = sess.created_at.replace(tzinfo=None) if sess.created_at.tzinfo else sess.created_at
                diff_mins = int(round((exp - crt).total_seconds() / 60.0))
                if diff_mins > 0:
                    duration_mins = diff_mins
        except Exception:
            duration_mins = 30

        result.append({
            "session_id": sess.session_id,
            "course_id": sess.material_id,
            "course_name": s.course_name or sess.material_id,
            "title": sess.title,
            "teacher_name": s.teacher_name or "المعلم",
            "is_active": sess.is_active,
            "duration_minutes": duration_mins,
            "created_at": sess.created_at.isoformat() if sess.created_at else None,
            "expires_at": sess.expires_at.isoformat() if sess.expires_at else None,
            "attendees_count": int(s.attendees_count or 0),
        })

    return result


# ── Storage Command Center (Vercel Blob / Neon Storage) Endpoints ─────────────

@router.get("/api/storage/quota")
@router.get("/storage/quota")
def get_storage_quota_admin(
    admin_id: Optional[int] = Depends(get_optional_admin_access),
    db: Session = Depends(get_db),
):
    """Retrieve live storage quota, total used bytes, and recoverable orphan files."""
    from app.services.storage_service import storage_service
    summary = storage_service.get_quota_summary(db)
    return {"quota": summary, **summary}


@router.get("/api/storage/files")
def get_storage_files_admin(
    filter: Optional[str] = Query(None),
    filter_mode: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    type_filter: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("size_desc"),
    page: int = Query(1, ge=1),
    limit: Optional[int] = Query(None, ge=1, le=100),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """List storage files sorted descending by size with smart filtering & linkage state."""
    from app.services.storage_service import storage_service
    resolved_filter = filter or filter_mode or "all"
    resolved_type = type or type_filter or "all"
    resolved_search = q or search
    resolved_limit = limit or page_size or 25

    return storage_service.list_files(
        db=db,
        filter_mode=resolved_filter,
        type_filter=resolved_type,
        search=resolved_search,
        sort=sort,
        page=page,
        page_size=resolved_limit,
    )


@router.post("/api/storage/upload-token")
@router.post("/api/storage/presign")
@router.post("/storage/presign")
def generate_client_upload_token_admin(
    payload: Dict[str, Any],
    admin_id: int = Depends(require_admin_access),
):
    """Generate signed client-side direct upload token to bypass Vercel Functions 4.5 MB limit."""
    from app.services.storage_service import storage_service
    filename = str(payload.get("filename") or "file.bin")
    content_type = str(payload.get("content_type") or "application/octet-stream")
    file_size = int(payload.get("file_size") or 0)
    return storage_service.generate_client_upload_token(
        filename=filename,
        content_type=content_type,
        file_size=file_size,
        admin_id=admin_id,
    )


@router.post("/api/storage/quarantine/{file_id}")
def quarantine_storage_file_admin(
    file_id: int,
    payload: Optional[Dict[str, Any]] = None,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Soft-delete file into 7-day quarantine without breaking system database links."""
    from app.services.storage_service import storage_service
    reason = (payload or {}).get("reason", "عزل مؤقت بواسطة المشرف")
    admin_user = user_svc.get_user_by_id(db, admin_id)
    admin_name = admin_user.name if admin_user else f"مسؤول #{admin_id}"
    try:
        return storage_service.quarantine_file(
            db=db,
            file_id=file_id,
            admin_id=admin_id,
            admin_name=admin_name,
            reason=reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/storage/restore/{file_id}")
def restore_storage_file_admin(
    file_id: int,
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Restore a quarantined file back to active operational state."""
    from app.services.storage_service import storage_service
    admin_user = user_svc.get_user_by_id(db, admin_id)
    admin_name = admin_user.name if admin_user else f"مسؤول #{admin_id}"
    try:
        return storage_service.restore_file(
            db=db,
            file_id=file_id,
            admin_id=admin_id,
            admin_name=admin_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/storage/quarantine/purge")
def purge_expired_quarantine_admin(
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Automatically purge all quarantined files whose 7-day retention period has expired."""
    from app.services.storage_service import storage_service
    admin_name = "مشرف النظام"
    u = user_svc.get_user_by_id(db, admin_id)
    if u:
        admin_name = u.name
    return storage_service.purge_expired_quarantined_files(
        db=db,
        admin_id=admin_id,
        admin_name=admin_name,
    )


@router.delete("/api/storage/permanent/{file_id}")
async def permanent_delete_file_admin(
    file_id: int,
    request: Request,
    confirmation: Optional[str] = Query(None, description="Must type DELETE"),
    admin_id: int = Depends(require_super_admin_access),
    db: Session = Depends(get_db),
):
    """Permanent immediate hard deletion (Restricted to SUPER_ADMIN with mandatory 'DELETE' confirmation)."""
    from app.services.storage_service import storage_service
    conf = confirmation
    if not conf:
        try:
            body = await request.json()
            conf = body.get("confirmation")
        except Exception:
            pass
    if not conf or conf.strip() != "DELETE":
        raise HTTPException(
            status_code=400,
            detail="لتأكيد الحذف النهائي غير القابل للتراجع، يجب إرسال confirmation='DELETE'."
        )

    admin_user = user_svc.get_user_by_id(db, admin_id)
    admin_name = admin_user.name if admin_user else f"مشرف أعلى #{admin_id}"
    try:
        res = storage_service.permanent_delete_file(
            db=db,
            file_id=file_id,
            admin_id=admin_id,
            admin_name=admin_name,
            confirmation=conf.strip(),
        )
        return {"success": True, **res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/storage/replace/{file_id}")
async def replace_storage_file_admin(
    file_id: int,
    request: Request,
    file: Optional[UploadFile] = File(None),
    new_url: Optional[str] = Form(None),
    new_size: Optional[int] = Form(None),
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Atomic replacement of file blob preserving all course/lecture references with net savings calculation."""
    from app.services.storage_service import storage_service
    from app.routers.content._helpers import save_file

    admin_user = user_svc.get_user_by_id(db, admin_id)
    admin_name = admin_user.name if admin_user else f"مسؤول #{admin_id}"

    resolved_path = None
    resolved_size = 0

    c_type = request.headers.get("content-type", "")
    if "application/json" in c_type:
        try:
            body = await request.json()
            resolved_path = body.get("new_url")
            resolved_size = int(body.get("new_size") or 0)
        except Exception:
            pass

    if not resolved_path:
        if new_url and new_size is not None:
            resolved_path = new_url
            resolved_size = new_size
        elif file:
            saved_path, saved_size = save_file(file)
            if not saved_path:
                raise HTTPException(status_code=400, detail="فشل رفع الملف البديل.")
            resolved_path = saved_path
            resolved_size = saved_size or 0

    if not resolved_path:
        raise HTTPException(status_code=400, detail="يرجى توفير ملف جديد أو رابط الرفع المباشر.")

    try:
        return storage_service.replace_file(
            db=db,
            file_id=file_id,
            admin_id=admin_id,
            admin_name=admin_name,
            new_file_path=resolved_path,
            new_file_size=resolved_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/storage/audit")
def get_storage_audit_logs_admin(
    limit: int = Query(50, ge=1, le=200),
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Retrieve immutable audit trail of all storage operations and reclaimed space."""
    from app.services.storage_service import storage_service
    logs = storage_service.get_audit_logs(db=db, limit=limit)
    return {"audit_logs": logs, "logs": logs}


@router.post("/api/storage/sync")
def sync_storage_admin(
    admin_id: int = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Trigger manual synchronization of storage tallies and Vercel Blob quota."""
    from app.services.storage_service import storage_service
    admin_name = None
    try:
        admin_user = user_svc.get_user_by_id(db, admin_id)
        if admin_user:
            admin_name = admin_user.name
    except Exception:
        pass
    return storage_service.trigger_sync(db, admin_id=admin_id, admin_name=admin_name)


# ── Admin Root Gateway & Dashboard Endpoint ───────────────────────────────────

_UM_HTML_FILE = os.path.join(os.path.dirname(__file__), "user_management.html")
_STORAGE_HTML_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "storage_command_center.html")
_DASHBOARD_HTML_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "dashboard.html")

if os.path.exists(_DASHBOARD_HTML_FILE):
    with open(_DASHBOARD_HTML_FILE, "r", encoding="utf-8") as _df:
        DASHBOARD_HTML = _df.read()
else:
    DASHBOARD_HTML = "<html><body><h1>Admin Dashboard</h1></body></html>"

@router.get("", response_model=None)
@router.get("/", response_model=None)
def get_dashboard_info(request: Request):
    """Return interactive web admin dashboard or administration API metadata."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept or "application/xhtml" in accept or "*/*" in accept or not accept:
        if os.path.exists(_UM_HTML_FILE):
            with open(_UM_HTML_FILE, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        elif os.path.exists(_STORAGE_HTML_FILE):
            with open(_STORAGE_HTML_FILE, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
    return {
        "service": "WE School Suez - Administration API Gateway",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "api_endpoints": "/admin/api",
        "storage_command_center": "/admin/storage",
        "docs": "/docs",
    }


@router.get("/storage", response_model=None)
def get_storage_dashboard(request: Request):
    """Return dedicated Storage Command Center (#UI-4.0) web dashboard."""
    if os.path.exists(_STORAGE_HTML_FILE):
        with open(_STORAGE_HTML_FILE, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    if os.path.exists(_UM_HTML_FILE):
        with open(_UM_HTML_FILE, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Storage Command Center</h1>")
