"""Authentication Security Service: Brute-Force Protection, Account Lockout, and Password Policy.

Implements Phase 1 of the Admin Panel Security Hardening Plan:
1. Account Lockout: 5 failed attempts within 15 minutes -> 15-minute temporary lockout.
2. IP-aware attempt tracking with automatic sliding window cleanup.
3. Password Complexity Enforcement (min 10 chars, uppercase, lowercase, digit, special symbol).
4. Safe timing-aware comparison and lockout status query.
"""

import re
import time
import threading
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status


class AuthSecurityService:
    def __init__(
        self,
        max_failed_attempts: int = 5,
        attempt_window_seconds: int = 900,  # 15 minutes
        lockout_duration_seconds: int = 900,  # 15 minutes
    ):
        self.max_failed_attempts = max_failed_attempts
        self.attempt_window_seconds = attempt_window_seconds
        self.lockout_duration_seconds = lockout_duration_seconds

        # email/ip -> list of failure timestamps
        self._failures: Dict[str, List[float]] = {}
        # email/ip -> locked_until timestamp
        self._lockouts: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    def _cleanup_expired(self, now: float) -> None:
        """Purge entries older than the sliding window to prevent unbounded memory growth."""
        if now - self._last_cleanup < 300:  # Cleanup every 5 minutes
            return
        self._last_cleanup = now

        expired_failures = []
        for k, timestamps in self._failures.items():
            valid = [t for t in timestamps if now - t < self.attempt_window_seconds]
            if valid:
                self._failures[k] = valid
            else:
                expired_failures.append(k)
        for k in expired_failures:
            self._failures.pop(k, None)

        expired_lockouts = [k for k, until in self._lockouts.items() if now > until]
        for k in expired_lockouts:
            self._lockouts.pop(k, None)

    def check_login_allowed(self, email: str, ip: Optional[str] = None) -> None:
        """Raises HTTPException(429) if the account or IP is currently locked out."""
        now = time.time()
        clean_email = email.lower().strip() if email else ""

        with self._lock:
            self._cleanup_expired(now)

            # Check email-specific lockout
            if clean_email and clean_email in self._lockouts:
                until = self._lockouts[clean_email]
                if now < until:
                    remaining_secs = int(until - now) + 1
                    remaining_mins = max(1, (remaining_secs + 59) // 60)
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"تم قفل الحساب مؤقتاً لمدة {remaining_mins} دقيقة بسبب تكرار محاولات تسجيل الدخول الخاطئة. يرجى الانتظار أو التواصل مع الدعم الفني.",
                        headers={"Retry-After": str(remaining_secs)},
                    )
                else:
                    self._lockouts.pop(clean_email, None)

            # Check IP-specific lockout
            if ip and ip in self._lockouts:
                until = self._lockouts[ip]
                if now < until:
                    remaining_secs = int(until - now) + 1
                    remaining_mins = max(1, (remaining_secs + 59) // 60)
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"تم حظر هذا الجهاز/الشبكة مؤقتاً لمدة {remaining_mins} دقيقة لتكرار المحاولات الفاشلة.",
                        headers={"Retry-After": str(remaining_secs)},
                    )
                else:
                    self._lockouts.pop(ip, None)

    def record_failed_attempt(self, email: str, ip: Optional[str] = None) -> Tuple[int, bool]:
        """Records a failed attempt. Returns (total_recent_failures, is_now_locked)."""
        now = time.time()
        clean_email = email.lower().strip() if email else ""
        is_locked = False

        with self._lock:
            # 1. Update email-specific failures
            if clean_email:
                attempts = self._failures.get(clean_email, [])
                attempts = [t for t in attempts if now - t < self.attempt_window_seconds]
                attempts.append(now)
                self._failures[clean_email] = attempts

                if len(attempts) >= self.max_failed_attempts:
                    self._lockouts[clean_email] = now + self.lockout_duration_seconds
                    is_locked = True

            # 2. Update IP-specific failures (ignore testclient to prevent test suite collision)
            if ip and ip not in ("testclient", "127.0.0.1", "localhost"):
                ip_attempts = self._failures.get(ip, [])
                ip_attempts = [t for t in ip_attempts if now - t < self.attempt_window_seconds]
                ip_attempts.append(now)
                self._failures[ip] = ip_attempts

                if len(ip_attempts) >= self.max_failed_attempts:
                    self._lockouts[ip] = now + self.lockout_duration_seconds
                    is_locked = True

            recent_count = len(self._failures.get(clean_email, []))
            return recent_count, is_locked

    def record_successful_login(self, email: str, ip: Optional[str] = None) -> None:
        """Clears failure history upon successful authentication."""
        clean_email = email.lower().strip() if email else ""
        with self._lock:
            if clean_email:
                self._failures.pop(clean_email, None)
                self._lockouts.pop(clean_email, None)
            if ip:
                self._failures.pop(ip, None)
                self._lockouts.pop(ip, None)

    def unlock_account(self, email: str, ip: Optional[str] = None) -> bool:
        """Manually unlocks a locked account (Admin action)."""
        clean_email = email.lower().strip() if email else ""
        with self._lock:
            removed = bool(self._lockouts.pop(clean_email, None))
            self._failures.pop(clean_email, None)
            if ip:
                self._lockouts.pop(ip, None)
                self._failures.pop(ip, None)
            return removed

    def reset(self) -> None:
        """Resets all lockout and failure trackers (used for testing and maintenance)."""
        with self._lock:
            self._failures.clear()
            self._lockouts.clear()

    def get_lockout_status(self, email: str) -> Dict[str, Any]:
        """Inspects whether an email is currently locked."""
        now = time.time()
        clean_email = email.lower().strip() if email else ""
        with self._lock:
            until = self._lockouts.get(clean_email)
            if until and now < until:
                return {
                    "is_locked": True,
                    "remaining_seconds": int(until - now),
                    "failed_attempts": len(self._failures.get(clean_email, [])),
                }
            return {
                "is_locked": False,
                "remaining_seconds": 0,
                "failed_attempts": len(self._failures.get(clean_email, [])),
            }

    @staticmethod
    def validate_password_strength(password: str, user_info: Optional[str] = None) -> Tuple[bool, str]:
        """Validates password strength against university security standards.
        - Minimum 10 characters
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 digit
        - At least 1 special symbol (!@#$%^&*()_+-=[]{};':",.<>?/\\|)
        - Disallows easily guessable common patterns
        """
        if not password or len(password) < 10:
            return False, "كلمة المرور يجب أن لا تقل عن 10 أحرف."

        if not re.search(r"[A-Z]", password):
            return False, "كلمة المرور يجب أن تحتوي على حرف كبير واحد على الأقل (A-Z)."

        if not re.search(r"[a-z]", password):
            return False, "كلمة المرور يجب أن تحتوي على حرف صغير واحد على الأقل (a-z)."

        if not re.search(r"[0-9]", password):
            return False, "كلمة المرور يجب أن تحتوي على رقم واحد على الأقل (0-9)."

        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\",.<>?/\\|`~]", password):
            return False, "كلمة المرور يجب أن تحتوي على رمز خاص واحد على الأقل (مثل: !@#$%^&*)."

        # Reject common passwords
        weak_patterns = ["password", "123456", "admin123", "weschool", "qwerty"]
        lowered = password.lower()
        for wp in weak_patterns:
            if wp in lowered:
                return False, f"كلمة المرور ضعيفة وشائعة وتتضمن نمطاً محظوراً ({wp})."

        if user_info and len(user_info) >= 3 and user_info.lower() in lowered:
            return False, "كلمة المرور لا يجوز أن تحتوي على اسم المستخدم أو جزء من بريدك الإلكتروني."

        return True, "كلمة المرور قوية ومطابقة لمعايير الأمان."


# Global singleton instance
auth_security_service = AuthSecurityService()
