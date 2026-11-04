from email.message import EmailMessage
import smtplib
import ssl

from app.core.config import OTP_EXPIRE_MINUTES, settings


_ISSUE_LABELS = {
    "technical": "Technical Issue",
    "course": "Problem with the material/course",
    "account": "Accounting problem",
    "general": "General suggestion or complaint",
}


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an HTML email using the configured SMTP server."""
    if not all((settings.SMTP_HOST, settings.SMTP_USERNAME, settings.SMTP_PASSWORD, settings.FROM_EMAIL)):
        print("[SMTP] Email is not configured; set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and FROM_EMAIL")
        return False

    message = EmailMessage()
    message["From"] = settings.FROM_EMAIL
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content("This email requires an HTML-capable email client.")
    message.add_alternative(html_body, subtype="html")

    try:
        context = ssl.create_default_context()
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context) as smtp:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
                smtp.starttls(context=context)
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                smtp.send_message(message)
        return True
    except Exception as exc:
        print(f"[SMTP] Failed to send email to {to_email}: {exc}")
        return False


def send_otp_email(to_email: str, otp: str, user_name: str) -> bool:
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
      <div style="background:#1565C0;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:24px;">WE School</h1>
        <p style="color:#90CAF9;margin:4px 0 0;">Password Reset Request</p>
      </div>
      <div style="background:#f5f7fa;padding:32px;border-radius:0 0 12px 12px;">
        <p style="color:#333;font-size:16px;">Hi <strong>{user_name}</strong>,</p>
        <p style="color:#555;">Use the verification code below to reset your password.
           It expires in <strong>{OTP_EXPIRE_MINUTES} minutes</strong>.</p>
        <div style="background:#fff;border:2px dashed #1565C0;border-radius:12px;text-align:center;padding:24px;margin:24px 0;">
          <span style="font-size:42px;letter-spacing:14px;font-weight:bold;color:#1565C0;font-family:monospace;">{otp}</span>
        </div>
        <p style="color:#999;font-size:13px;">If you did not request a password reset, you can safely ignore this email.</p>
        <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
        <p style="color:#bbb;font-size:12px;text-align:center;">WE School &mdash; WE Applied Technology Schools</p>
      </div>
    </div>
    """
    return _send_email(to_email, "WE School – Your Password Reset Code", html_body)


def send_contact_us_email(
    user_name: str,
    user_email: str,
    issue_type: str,
    subject: str,
    message: str,
) -> bool:
    issue_label = _ISSUE_LABELS.get(issue_type, issue_type)
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;">
      <div style="background:#1565C0;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:22px;">WE School — Contact Us</h1>
        <p style="color:#90CAF9;margin:4px 0 0;">New message from a user</p>
      </div>
      <div style="background:#f5f7fa;padding:32px;border-radius:0 0 12px 12px;">
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
          <tr><td style="padding:8px 12px;background:#e3eaf5;font-weight:bold;width:140px;">Name</td><td style="padding:8px 12px;">{user_name}</td></tr>
          <tr><td style="padding:8px 12px;background:#e3eaf5;font-weight:bold;">Email</td><td style="padding:8px 12px;">{user_email}</td></tr>
          <tr><td style="padding:8px 12px;background:#e3eaf5;font-weight:bold;">Type of problem</td><td style="padding:8px 12px;">{issue_label}</td></tr>
          <tr><td style="padding:8px 12px;background:#e3eaf5;font-weight:bold;">Topic</td><td style="padding:8px 12px;">{subject}</td></tr>
        </table>
        <div style="background:#fff;border-right:4px solid #1565C0;padding:16px 20px;border-radius:4px;color:#333;line-height:1.7;white-space:pre-wrap;">{message}</div>
        <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
        <p style="color:#bbb;font-size:12px;text-align:center;">WE School &mdash; WE Applied Technology Schools</p>
      </div>
    </div>
    """
    return _send_email(settings.FROM_EMAIL, f"[WE School] {issue_label} — {subject}", html_body)


def send_welcome_email(to_email: str, user_name: str) -> bool:
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
      <div style="background:#1565C0;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;">Welcome to WE School!</h1>
      </div>
      <div style="background:#f5f7fa;padding:32px;border-radius:0 0 12px 12px;">
        <p style="color:#333;font-size:16px;">Hi <strong>{user_name}</strong>,</p>
        <p style="color:#555;">Your account has been created successfully. You can now connect with teachers, School Admins, and fellow students on WE School.</p>
        <p style="color:#555;">Start exploring your courses and joining the community!</p>
        <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
        <p style="color:#bbb;font-size:12px;text-align:center;">WE School &mdash; WE Applied Technology Schools</p>
      </div>
    </div>
    """
    return _send_email(to_email, "Welcome to WE School 🎓", html_body)


def send_password_changed_email(to_email: str, user_name: str) -> bool:
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
      <div style="background:#1565C0;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:24px;">WE School</h1>
        <p style="color:#90CAF9;margin:4px 0 0;">Password Changed</p>
      </div>
      <div style="background:#f5f7fa;padding:32px;border-radius:0 0 12px 12px;">
        <p style="color:#333;font-size:16px;">Hi <strong>{user_name}</strong>,</p>
        <p style="color:#555;">Your password has been changed successfully. If you did not make this change, please contact support immediately.</p>
        <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
        <p style="color:#bbb;font-size:12px;text-align:center;">WE School &mdash; WE Applied Technology Schools</p>
      </div>
    </div>
    """
    return _send_email(to_email, "WE School – Password Changed", html_body)
