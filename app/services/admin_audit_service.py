"""Admin Audit Logging Service.

Provides a unified interface for recording security and administrative actions,
as well as querying recent audit events.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import desc
from sqlalchemy.orm import Session
from app.models.admin_audit import AdminAuditLog


class AdminAuditService:
    @staticmethod
    def log_action(
        db: Session,
        action: str,
        admin_id: Optional[int] = None,
        admin_email: Optional[str] = None,
        admin_name: Optional[str] = None,
        target_resource: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[str] = None,
    ) -> AdminAuditLog:
        """Records an administrative action in the immutable audit log."""
        log_entry = AdminAuditLog(
            admin_id=admin_id,
            admin_email=admin_email,
            admin_name=admin_name,
            action=action,
            target_resource=target_resource,
            ip_address=ip_address,
            user_agent=user_agent[:255] if user_agent else None,
            details=details,
        )
        try:
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)
        except Exception:
            db.rollback()
        return log_entry

    @staticmethod
    def get_recent_logs(
        db: Session,
        limit: int = 50,
        action: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries recent audit log entries in reverse chronological order."""
        query = db.query(AdminAuditLog)
        if action:
            query = query.filter(AdminAuditLog.action == action)
        entries = query.order_by(desc(AdminAuditLog.created_at)).limit(limit).all()

        return [
            {
                "id": e.id,
                "admin_id": e.admin_id,
                "admin_email": e.admin_email,
                "admin_name": e.admin_name,
                "action": e.action,
                "target_resource": e.target_resource,
                "ip_address": e.ip_address,
                "user_agent": e.user_agent,
                "details": e.details,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]


admin_audit_service = AdminAuditService()
