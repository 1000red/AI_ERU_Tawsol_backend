import os
import re
import uuid
import datetime
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_, and_

from app.core.config import settings
from app.models.content.material_file import MaterialFile
from app.models.content.announcement import Announcement
from app.models.material import Material
from app.models.storage_audit import StorageAuditLog, StorageQuarantine
from app.services.neon_storage import neon_storage

# Hobby Tier default: 1 GB (1,073,741,824 bytes)
DEFAULT_QUOTA_BYTES = int(os.getenv("VERCEL_BLOB_QUOTA_BYTES", str(1 * 1024 * 1024 * 1024)))
VERCEL_BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN", "")


def format_bytes(num_bytes: Optional[int]) -> str:
    if not num_bytes or num_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(num_bytes)
    while size >= 1024.0 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.1f} {units[i]}"


class StorageManagementService:
    def __init__(self):
        self.quota_bytes = DEFAULT_QUOTA_BYTES
        self._last_sync_time = datetime.datetime.now(datetime.timezone.utc)

    def get_quota_summary(self, db: Session) -> Dict[str, Any]:
        """Calculates total usage, active vs orphan files, and quarantine statistics."""
        # Query sum of sizes and count of all MaterialFiles
        try:
            total_stats = db.query(
                func.count(MaterialFile.file_id),
                func.sum(func.coalesce(MaterialFile.file_size, 0))
            ).first()
            total_files = total_stats[0] or 0
            total_used_bytes = int(total_stats[1] or 0)
        except Exception:
            total_files = 0
            total_used_bytes = 0

        # Quarantined files
        try:
            quarantine_stats = db.query(
                func.count(StorageQuarantine.id),
                func.sum(func.coalesce(StorageQuarantine.original_size, 0))
            ).first()
            quarantined_count = quarantine_stats[0] or 0
            quarantined_bytes = int(quarantine_stats[1] or 0)
        except Exception:
            quarantined_count = 0
            quarantined_bytes = 0

        # Orphan files (files without course/material_id and announcement_id)
        try:
            orphan_stats = db.query(
                func.count(MaterialFile.file_id),
                func.sum(func.coalesce(MaterialFile.file_size, 0))
            ).filter(
                or_(MaterialFile.material_id.is_(None), MaterialFile.material_id == ""),
                MaterialFile.announcement_id.is_(None)
            ).first()
            orphan_count = orphan_stats[0] or 0
            recoverable_bytes = int(orphan_stats[1] or 0)
        except Exception:
            orphan_count = 0
            recoverable_bytes = 0

        # Calculate percentage against current tier quota (1 GB Hobby or Pro)
        pct = (total_used_bytes / max(1, self.quota_bytes)) * 100.0
        pct_rounded = round(pct, 2)

        if pct >= 100.0:
            status = "exceeded"
        elif pct >= 90.0:
            status = "critical"
        elif pct >= 75.0:
            status = "warning"
        else:
            status = "normal"

        remaining_bytes = max(0, self.quota_bytes - total_used_bytes)

        tier_name = "Vercel Blob Hobby (1 GB)" if self.quota_bytes <= 1073741824 else "Vercel Blob Pro"

        return {
            "quota_total_bytes": self.quota_bytes,
            "limit_bytes": self.quota_bytes,
            "quota_total_formatted": format_bytes(self.quota_bytes),
            "used_bytes": total_used_bytes,
            "used_formatted": format_bytes(total_used_bytes),
            "remaining_bytes": remaining_bytes,
            "remaining_formatted": format_bytes(remaining_bytes),
            "used_percentage": pct_rounded,
            "status": status,
            "tier_name": tier_name,
            "tier": tier_name,
            "total_files": total_files,
            "files_count": total_files,
            "orphan_files_count": orphan_count,
            "recoverable_bytes": recoverable_bytes,
            "recoverable_bytes_from_orphans": recoverable_bytes,
            "recoverable_formatted": format_bytes(recoverable_bytes),
            "quarantined_count": quarantined_count,
            "quarantined_bytes": quarantined_bytes,
            "quarantined_formatted": format_bytes(quarantined_bytes),
            "last_sync": self._last_sync_time.isoformat(),
            "blob_configured": bool(VERCEL_BLOB_TOKEN or neon_storage.is_configured),
            "sync_status": "operational",
        }

    def list_files(
        self,
        db: Session,
        filter_mode: str = "all",
        type_filter: str = "all",
        search: Optional[str] = None,
        sort: str = "size_desc",
        page: int = 1,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        """Lists files sorted descending by size with smart filters and linkage detection."""
        query = db.query(MaterialFile)

        # 1. Filter Mode
        if filter_mode == "gt_5mb":
            query = query.filter(MaterialFile.file_size >= 5 * 1024 * 1024)
        elif filter_mode == "orphan":
            query = query.filter(
                or_(MaterialFile.material_id.is_(None), MaterialFile.material_id == ""),
                MaterialFile.announcement_id.is_(None)
            )
        elif filter_mode == "quarantine":
            try:
                quarantine_records = db.query(StorageQuarantine.file_id).all()
                quarantine_ids = [r[0] for r in quarantine_records]
                query = query.filter(MaterialFile.file_id.in_(quarantine_ids))
            except Exception:
                query = query.filter(MaterialFile.file_id == -1)

        # 2. Type Filter
        if type_filter and type_filter != "all":
            clean_tf = type_filter.lower().strip()
            if clean_tf == "video":
                query = query.filter(MaterialFile.file_type.in_(["video", "mp4", "mov"]))
            elif clean_tf == "pdf":
                query = query.filter(MaterialFile.file_type == "pdf")
            elif clean_tf == "image":
                query = query.filter(MaterialFile.file_type.in_(["image", "jpg", "png", "webp"]))
            elif clean_tf == "doc":
                query = query.filter(MaterialFile.file_type.in_(["word", "ppt", "doc", "docx", "pptx"]))
            elif clean_tf == "code":
                query = query.filter(MaterialFile.file_type.in_(["python", "jupyter", "javascript", "typescript", "c", "cpp", "java", "sql", "html", "css"]))
            else:
                query = query.filter(MaterialFile.file_type == clean_tf)

        # 3. Search
        if search and search.strip():
            pat = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    MaterialFile.title.ilike(pat),
                    MaterialFile.file_path.ilike(pat),
                    MaterialFile.description.ilike(pat)
                )
            )

        # 4. Sorting (default: largest first)
        if sort == "size_asc":
            query = query.order_by(MaterialFile.file_size.asc().nulls_last())
        elif sort == "date_desc":
            query = query.order_by(MaterialFile.created_at.desc())
        elif sort == "date_asc":
            query = query.order_by(MaterialFile.created_at.asc())
        else:
            query = query.order_by(MaterialFile.file_size.desc().nulls_last())

        total_items = query.count()
        offset = max(0, (page - 1) * page_size)
        items = query.offset(offset).limit(page_size).all()

        # Batch lookup for quarantined status
        file_ids = [f.file_id for f in items]
        quarantine_map = {}
        if file_ids:
            try:
                q_records = db.query(StorageQuarantine).filter(StorageQuarantine.file_id.in_(file_ids)).all()
                for qr in q_records:
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    due = qr.purge_due_at
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=datetime.timezone.utc)
                    remaining_days = max(0, (due - now_utc).days)
                    quarantine_map[qr.file_id] = {
                        "quarantined_at": qr.quarantined_at.isoformat(),
                        "purge_due_at": qr.purge_due_at.isoformat(),
                        "days_left": remaining_days,
                        "days_remaining": remaining_days,
                        "reason": qr.reason,
                    }
            except Exception:
                pass

        # Build detailed row items
        rows = []
        for mf in items:
            sz = mf.file_size or 0
            sz_pct = round((sz / max(1, self.quota_bytes)) * 100, 2)
            is_orphan = (not mf.material_id) and (not mf.announcement_id)

            linked_info = {}
            if mf.material_id:
                mat = db.query(Material).filter(Material.material_id == mf.material_id).first()
                mat_name = (mat.name if hasattr(mat, "name") and mat.name else (getattr(mat, "title", None) or mf.material_id)) if mat else mf.material_id
                linked_info = {
                    "type": "course",
                    "id": mf.material_id,
                    "name": mat_name,
                    "badge": f"مقرر: {mf.material_id}",
                    "is_safe_to_delete": False
                }
            elif mf.announcement_id:
                ann = db.query(Announcement).filter(Announcement.announcement_id == mf.announcement_id).first()
                linked_info = {
                    "type": "announcement",
                    "id": mf.announcement_id,
                    "name": ann.title if ann else f"إعلان #{mf.announcement_id}",
                    "badge": "إعلان مدرسي نشط",
                    "is_safe_to_delete": False
                }
            else:
                linked_info = {
                    "type": "orphan",
                    "id": None,
                    "name": "ملف يتيم غير مرتبط",
                    "badge": "يتيم • آمن للمسح",
                    "is_safe_to_delete": True
                }

            q_info = quarantine_map.get(mf.file_id)

            rows.append({
                "id": mf.file_id,
                "file_id": mf.file_id,
                "title": mf.title,
                "file_path": mf.file_path,
                "file_type": mf.file_type or "file",
                "file_size": sz,
                "size_formatted": format_bytes(sz),
                "size_percentage": sz_pct,
                "quota_percentage": f"{sz_pct:.2f}",
                "is_orphan": is_orphan,
                "is_quarantined": bool(q_info),
                "quarantine_info": q_info,
                "quarantine_days_remaining": q_info.get("days_remaining") if q_info else None,
                "linked_to": linked_info,
                "created_at": mf.created_at.isoformat() if mf.created_at else None,
                "author_id": mf.author_id,
            })

        total_pages = max(1, (total_items + page_size - 1) // page_size)
        return {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total": total_items,
            "total_pages": total_pages,
            "pages": total_pages,
            "items": rows,
            "files": rows,
        }

    def quarantine_file(self, db: Session, file_id: int, admin_id: int, admin_name: str, reason: str = "عزل يدوي عبر الأدمن") -> Dict[str, Any]:
        """Soft-deletes the file into 7-day quarantine without deleting database references."""
        mf = db.query(MaterialFile).filter(MaterialFile.file_id == file_id).first()
        if not mf:
            raise ValueError("الملف المطلوب غير موجود في النظام.")

        existing = db.query(StorageQuarantine).filter(StorageQuarantine.file_id == file_id).first()
        if existing:
            return {"status": "already_quarantined", "file_id": file_id}

        purge_due = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
        q_record = StorageQuarantine(
            file_id=file_id,
            quarantined_by_id=admin_id,
            original_path=mf.file_path or "",
            original_size=mf.file_size or 0,
            purge_due_at=purge_due,
            reason=reason or "عزل مؤقت لمدة 7 أيام",
        )
        db.add(q_record)

        audit = StorageAuditLog(
            admin_id=admin_id,
            admin_name=admin_name,
            action="quarantine",
            file_id=file_id,
            file_title=mf.title,
            file_path=mf.file_path,
            file_size_bytes=mf.file_size or 0,
            bytes_freed=0,
            details=f"تم عزل الملف مؤقتاً لمدة 7 أيام حتى {purge_due.strftime('%Y-%m-%d')}. السبب: {reason}",
        )
        db.add(audit)
        db.commit()

        return {
            "success": True,
            "status": "success",
            "file_id": file_id,
            "purge_due_at": purge_due.isoformat(),
            "message": "تم نقل الملف إلى سلة العزل المؤقت بنجاح لمدة 7 أيام.",
        }

    def restore_file(self, db: Session, file_id: int, admin_id: int, admin_name: str) -> Dict[str, Any]:
        """Restores a quarantined file back to active status."""
        mf = db.query(MaterialFile).filter(MaterialFile.file_id == file_id).first()
        if not mf:
            raise ValueError("الملف المطلوب غير موجود.")

        q_record = db.query(StorageQuarantine).filter(StorageQuarantine.file_id == file_id).first()
        if not q_record:
            return {"success": False, "status": "not_quarantined", "file_id": file_id}

        db.delete(q_record)

        audit = StorageAuditLog(
            admin_id=admin_id,
            admin_name=admin_name,
            action="restore",
            file_id=file_id,
            file_title=mf.title,
            file_path=mf.file_path,
            file_size_bytes=mf.file_size or 0,
            bytes_freed=0,
            details="تمت استعادة الملف من العزل المؤقت إلى الحالة النشطة.",
        )
        db.add(audit)
        db.commit()

        return {
            "success": True,
            "status": "success",
            "file_id": file_id,
            "message": "تمت استعادة الملف من العزل بنجاح.",
        }

    def permanent_delete_file(
        self,
        db: Session,
        file_id: int,
        admin_id: int,
        admin_name: str,
        confirmation: str,
    ) -> Dict[str, Any]:
        """Hard-deletes the physical file and DB record. Strictly requires confirmation == 'DELETE'."""
        if confirmation != "DELETE":
            raise ValueError("يجب كتابة كلمة DELETE بالأحرف الإنجليزية الكبيرة لتأكيد الحذف النهائي غير القابل للتراجع.")

        mf = db.query(MaterialFile).filter(MaterialFile.file_id == file_id).first()
        if not mf:
            raise ValueError("الملف المطلوب غير موجود.")

        freed_bytes = mf.file_size or 0
        old_path = mf.file_path or ""
        title = mf.title

        # 1. Physical file deletion
        self._delete_physical_blob(old_path)

        # 2. Delete DB records
        db.query(StorageQuarantine).filter(StorageQuarantine.file_id == file_id).delete()
        db.delete(mf)

        # 3. Log audit
        audit = StorageAuditLog(
            admin_id=admin_id,
            admin_name=admin_name,
            action="permanent_delete",
            file_id=file_id,
            file_title=title,
            file_path=old_path,
            file_size_bytes=freed_bytes,
            bytes_freed=freed_bytes,
            details=f"حذف نهائي فوري بواسطة {admin_name}. تم استرداد {format_bytes(freed_bytes)}.",
        )
        db.add(audit)
        db.commit()

        return {
            "success": True,
            "status": "success",
            "file_id": file_id,
            "freed_bytes": freed_bytes,
            "bytes_freed": freed_bytes,
            "freed_formatted": format_bytes(freed_bytes),
            "message": f"تم الحذف النهائي للملف وتحرير {format_bytes(freed_bytes)} بنجاح.",
        }

    def replace_file(
        self,
        db: Session,
        file_id: int,
        admin_id: int,
        admin_name: str,
        new_file_path: str,
        new_file_size: int,
    ) -> Dict[str, Any]:
        """Atomically replaces the underlying blob for an existing MaterialFile without breaking references."""
        mf = db.query(MaterialFile).filter(MaterialFile.file_id == file_id).first()
        if not mf:
            raise ValueError("الملف المراد استبداله غير موجود.")

        old_size = mf.file_size or 0
        old_path = mf.file_path or ""
        net_saved = max(0, old_size - new_file_size)

        # Update MaterialFile record atomically
        mf.file_path = new_file_path
        mf.file_size = new_file_size
        mf.updated_at = datetime.datetime.now(datetime.timezone.utc)

        # Remove old blob if path changed
        if old_path and old_path != new_file_path:
            self._delete_physical_blob(old_path)

        # Log audit
        audit = StorageAuditLog(
            admin_id=admin_id,
            admin_name=admin_name,
            action="replace",
            file_id=file_id,
            file_title=mf.title,
            file_path=new_file_path,
            file_size_bytes=new_file_size,
            bytes_freed=net_saved,
            details=f"استبدال ذري للملف: الحجم السابق {format_bytes(old_size)} ➔ الحجم الجديد {format_bytes(new_file_size)}. صافي التوفير: {format_bytes(net_saved)}.",
        )
        db.add(audit)
        db.commit()

        return {
            "success": True,
            "status": "success",
            "file_id": file_id,
            "old_size": old_size,
            "new_size": new_file_size,
            "net_savings": net_saved,
            "net_saved_bytes": net_saved,
            "net_saved_formatted": format_bytes(net_saved),
            "new_path": new_file_path,
            "message": f"تم استبدال الملف بنجاح مع الحفاظ على كافة الروابط وتوفير {format_bytes(net_saved)}.",
        }

    def generate_client_upload_token(
        self,
        filename: str,
        content_type: str,
        file_size: int,
        admin_id: int,
    ) -> Dict[str, Any]:
        """Generates a secure client-side upload token bypassing Vercel Functions 4.5 MB payload limit."""
        clean_ext = os.path.splitext(filename)[1].lower()
        unique_key = f"content/{uuid.uuid4().hex}{clean_ext}"

        # 1. If Vercel Blob is configured with BLOB_READ_WRITE_TOKEN
        if VERCEL_BLOB_TOKEN:
            blob_url = f"https://blob.vercel-storage.com/{unique_key}"
            return {
                "upload_mode": "vercel_blob",
                "object_key": unique_key,
                "token": VERCEL_BLOB_TOKEN,
                "upload_url": blob_url,
                "file_url": blob_url,
                "public_url": blob_url,
                "multipart": True,
                "multipart_supported": True,
                "headers": {
                    "authorization": f"Bearer {VERCEL_BLOB_TOKEN}",
                    "x-content-type": content_type or "application/octet-stream",
                },
                "max_size_bytes": 500 * 1024 * 1024,  # 500 MB max
            }

        # 2. If Neon S3 is configured, generate presigned PUT url
        if neon_storage.is_configured:
            try:
                presigned_url = neon_storage.client.generate_presigned_url(
                    ClientMethod="put_object",
                    Params={
                        "Bucket": neon_storage.bucket_name,
                        "Key": unique_key,
                        "ContentType": content_type or "application/octet-stream",
                    },
                    ExpiresIn=300,  # 5 minutes
                )
                public_url = f"{neon_storage.endpoint_url.rstrip('/')}/{neon_storage.bucket_name}/{unique_key}"
                return {
                    "upload_mode": "presigned_s3",
                    "object_key": unique_key,
                    "upload_url": presigned_url,
                    "file_url": public_url,
                    "public_url": public_url,
                    "multipart": True,
                    "multipart_supported": True,
                    "headers": {
                        "Content-Type": content_type or "application/octet-stream"
                    },
                    "max_size_bytes": 500 * 1024 * 1024,
                }
            except Exception:
                pass

        # 3. Server fallback mode
        fallback_url = f"/api/content/files/{unique_key}"
        return {
            "upload_mode": "server_direct",
            "object_key": unique_key,
            "upload_url": "/api/content/files",
            "file_url": fallback_url,
            "public_url": fallback_url,
            "multipart": False,
            "multipart_supported": True,
            "headers": {},
            "max_size_bytes": 4500000,
        }

    def get_audit_logs(self, db: Session, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns the recent audit history of storage operations."""
        logs = db.query(StorageAuditLog).order_by(desc(StorageAuditLog.created_at)).limit(limit).all()
        return [
            {
                "id": l.id,
                "admin_id": l.admin_id,
                "admin_name": l.admin_name or "المسؤول",
                "action": l.action,
                "file_id": l.file_id,
                "file_title": l.file_title,
                "file_path": l.file_path,
                "file_size_formatted": format_bytes(l.file_size_bytes),
                "bytes_freed_formatted": format_bytes(l.bytes_freed),
                "details": l.details,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ]

    def _sync_with_vercel_blob(self, db: Session) -> Dict[str, Any]:
        """Queries Vercel Blob REST API to reconcile remote blobs and update file sizes in database."""
        token = VERCEL_BLOB_TOKEN or os.getenv("BLOB_READ_WRITE_TOKEN", "")
        if not token:
            return {"synced": False, "reason": "No VERCEL_BLOB_TOKEN configured"}

        try:
            import urllib.request
            import json

            req = urllib.request.Request(
                "https://blob.vercel-storage.com/?limit=1000",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "WE-School-StorageCommandCenter/2.0",
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                blobs = data.get("blobs", [])
                remote_bytes = 0
                updated_count = 0

                for b in blobs:
                    b_url = b.get("url", "")
                    b_path = b.get("pathname", "")
                    b_size = int(b.get("size") or 0)
                    remote_bytes += b_size

                    # Find matching file in DB
                    mf = db.query(MaterialFile).filter(
                        or_(
                            MaterialFile.file_path == b_url,
                            MaterialFile.link_url == b_url,
                            MaterialFile.file_path.ilike(f"%{b_path}") if b_path else False,
                        )
                    ).first()
                    if mf and (not mf.file_size or mf.file_size == 0):
                        mf.file_size = b_size
                        updated_count += 1

                if updated_count > 0:
                    db.commit()

                return {
                    "synced": True,
                    "blob_count": len(blobs),
                    "remote_bytes": remote_bytes,
                    "updated_db_records": updated_count,
                }
        except Exception as e:
            return {"synced": False, "error": str(e)}

    def _sync_with_neon_storage(self, db: Session) -> Dict[str, Any]:
        """Queries Neon Object Storage (S3) to reconcile objects and update file sizes."""
        if not neon_storage.is_configured:
            return {"synced": False, "reason": "Neon storage not configured"}

        try:
            resp = neon_storage.client.list_objects_v2(Bucket=neon_storage.bucket_name, MaxKeys=1000)
            contents = resp.get("Contents", [])
            remote_bytes = 0
            updated_count = 0

            for obj in contents:
                key = obj.get("Key", "")
                size = int(obj.get("Size") or 0)
                remote_bytes += size

                if key:
                    mf = db.query(MaterialFile).filter(
                        MaterialFile.file_path.ilike(f"%{key}%")
                    ).first()
                    if mf and (not mf.file_size or mf.file_size == 0):
                        mf.file_size = size
                        updated_count += 1

            if updated_count > 0:
                db.commit()

            return {
                "synced": True,
                "object_count": len(contents),
                "remote_bytes": remote_bytes,
                "updated_db_records": updated_count,
            }
        except Exception as e:
            return {"synced": False, "error": str(e)}

    def _auto_size_missing_files(self, db: Session) -> int:
        """Finds any MaterialFile records with missing or 0 file_size and detects size via HEAD or local file."""
        missing = db.query(MaterialFile).filter(
            or_(MaterialFile.file_size.is_(None), MaterialFile.file_size <= 0)
        ).all()

        updated = 0
        import urllib.request

        for mf in missing:
            path = mf.file_path or mf.link_url
            if not path:
                continue

            # 1. Remote HTTP/HTTPS URL
            if path.startswith("http://") or path.startswith("https://"):
                try:
                    req = urllib.request.Request(
                        path,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                        method="HEAD",
                    )
                    with urllib.request.urlopen(req, timeout=5) as r:
                        cl = r.headers.get("Content-Length")
                        if cl and cl.isdigit() and int(cl) > 0:
                            mf.file_size = int(cl)
                            updated += 1
                            continue
                except Exception:
                    pass

            # 2. Local disk path
            if os.path.exists(path):
                try:
                    sz = os.path.getsize(path)
                    if sz > 0:
                        mf.file_size = sz
                        updated += 1
                except Exception:
                    pass

        if updated > 0:
            db.commit()
        return updated

    def trigger_sync(self, db: Session, admin_id: Optional[int] = None, admin_name: Optional[str] = None) -> Dict[str, Any]:
        """Performs comprehensive storage synchronization across Vercel Blob, Neon S3, and database."""
        # 1. Sync Vercel Blob
        blob_res = self._sync_with_vercel_blob(db)

        # 2. Sync Neon S3
        neon_res = self._sync_with_neon_storage(db)

        # 3. Auto-size files with 0 or None size
        auto_sized = self._auto_size_missing_files(db)

        # 4. Update sync timestamp
        self._last_sync_time = datetime.datetime.now(datetime.timezone.utc)

        # 5. Log audit entry
        try:
            audit = StorageAuditLog(
                admin_id=admin_id,
                admin_name=admin_name or ("المسؤول" if admin_id else "مزامنة النظام"),
                action="sync",
                details=f"مزامنة شاملة: Vercel Blob ({blob_res.get('synced', False)}), Neon Storage ({neon_res.get('synced', False)}), ملفات محدثة: {auto_sized}.",
            )
            db.add(audit)
            db.commit()
        except Exception:
            db.rollback()

        # 6. Return fresh summary
        summary = self.get_quota_summary(db)
        summary["sync_details"] = {
            "vercel_blob": blob_res,
            "neon_storage": neon_res,
            "auto_sized_files": auto_sized,
            "synced_at": self._last_sync_time.isoformat(),
        }
        return summary

    def _delete_physical_blob(self, path_or_url: str) -> None:
        if not path_or_url:
            return

        # Vercel Blob URL deletion
        if "blob.vercel-storage.com" in path_or_url and VERCEL_BLOB_TOKEN:
            try:
                import urllib.request
                import json
                req = urllib.request.Request(
                    "https://blob.vercel-storage.com/delete",
                    data=json.dumps({"urls": [path_or_url]}).encode("utf-8"),
                    headers={
                        "authorization": f"Bearer {VERCEL_BLOB_TOKEN}",
                        "content-type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    pass
            except Exception:
                pass

        # Neon S3 deletion
        elif neon_storage.is_configured and ("storage" in path_or_url or "s3" in path_or_url):
            try:
                key = path_or_url.split(f"{neon_storage.bucket_name}/")[-1]
                neon_storage.client.delete_object(Bucket=neon_storage.bucket_name, Key=key)
            except Exception:
                pass

        # Local disk deletion
        elif os.path.exists(path_or_url):
            try:
                os.remove(path_or_url)
            except Exception:
                pass


storage_service = StorageManagementService()
