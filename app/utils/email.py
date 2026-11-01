from app.core.config import settings

# Issue type labels shown in the email subject/body
_ISSUE_LABELS = {
    "technical":  "Technical Issue",
    "course":     "Problem with the material/course",
    "account":    "Accounting problem",
    "general":    "General suggestion or complaint",
}


def send_otp_email(to_email: str, otp: str, user_name: str) -> bool:
    if not settings.SENDGRID_API_KEY:
        print(f"[DEV EMAIL] OTP for {to_email} ({user_name}): {otp}")
        return True

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
      <div style="background:#1565C0;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:24px;">AI Connect</h1>
        <p style="color:#90CAF9;margin:4px 0 0;">Password Reset Request</p>
      </div>
      <div style="background:#f5f7fa;padding:32px;border-radius:0 0 12px 12px;">
        <p style="color:#333;font-size:16px;">Hi <strong>{user_name}</strong>,</p>
        <p style="color:#555;">Use the verification code below to reset your password.
           It expires in <strong>{settings.OTP_EXPIRE_MINUTES} minutes</strong>.</p>
        <div style="background:#fff;border:2px dashed #1565C0;border-radius:12px;
                    text-align:center;padding:24px;margin:24px 0;">
          <span style="font-size:42px;letter-spacing:14px;font-weight:bold;
                       color:#1565C0;font-family:monospace;">{otp}</span>
        </div>
        <p style="color:#999;font-size:13px;">
          If you did not request a password reset, you can safely ignore this email.
        </p>
        <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
        <p style="color:#bbb;font-size:12px;text-align:center;">
          AI Connect &mdash; El Ryada University Community Platform
        </p>
      </div>
    </div>
    """

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=settings.FROM_EMAIL,
            to_emails=to_email,
            subject="AI Connect – Your Password Reset Code",
            html_content=html_body,
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code in (200, 202)
    except Exception as e:
        print(f"[SendGrid] Failed to send email to {to_email}: {e}")
        return False


def send_contact_us_email(
    user_name: str,
    user_email: str,
    issue_type: str,
    subject: str,
    message: str,
) -> bool:
    issue_label = _ISSUE_LABELS.get(issue_type, issue_type)

    if not settings.SENDGRID_API_KEY:
        print(
            f"[DEV EMAIL] Contact Us from {user_email} ({user_name}) | "
            f"Type: {issue_label} | Subject: {subject}\n{message}"
        )
        return True

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;">
      <div style="background:#1565C0;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:22px;">AI Connect — Contact Us</h1>
        <p style="color:#90CAF9;margin:4px 0 0;">New message from a user</p>
      </div>
      <div style="background:#f5f7fa;padding:32px;border-radius:0 0 12px 12px;">

        <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
          <tr>
            <td style="padding:8px 12px;background:#e3eaf5;font-weight:bold;width:140px;border-radius:4px;">Name</td>
            <td style="padding:8px 12px;">{user_name}</td>
          </tr>
          <tr>
            <td style="padding:8px 12px;background:#e3eaf5;font-weight:bold;border-radius:4px;">Email</td>
            <td style="padding:8px 12px;">{user_email}</td>
          </tr>
          <tr>
            <td style="padding:8px 12px;background:#e3eaf5;font-weight:bold;border-radius:4px;">Type of problem</td>
            <td style="padding:8px 12px;">{issue_label}</td>
          </tr>
          <tr>
            <td style="padding:8px 12px;background:#e3eaf5;font-weight:bold;border-radius:4px;">the topic</td>
            <td style="padding:8px 12px;">{subject}</td>
          </tr>
        </table>

        <div style="background:#fff;border-right:4px solid #1565C0;padding:16px 20px;
                    border-radius:4px;color:#333;line-height:1.7;white-space:pre-wrap;">
{message}
        </div>

        <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
        <p style="color:#bbb;font-size:12px;text-align:center;">
          AI Connect &mdash; El Ryada University Community Platform
        </p>
      </div>
    </div>
    """

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message_obj = Mail(
            from_email=settings.FROM_EMAIL,
            to_emails=settings.FROM_EMAIL,
            subject=f"[AI Connect] {issue_label} — {subject}",
            html_content=html_body,
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message_obj)
        return response.status_code in (200, 202)
    except Exception as e:
        print(f"[SendGrid] Contact Us email failed: {e}")
        return False


def send_welcome_email(to_email: str, user_name: str) -> bool:
    if not settings.SENDGRID_API_KEY:
        print(f"[DEV EMAIL] Welcome email for {to_email} ({user_name})")
        return True

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
      <div style="background:#1565C0;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;">Welcome to AI Connect!</h1>
      </div>
      <div style="background:#f5f7fa;padding:32px;border-radius:0 0 12px 12px;">
        <p style="color:#333;font-size:16px;">Hi <strong>{user_name}</strong>,</p>
        <p style="color:#555;">
          Your account has been created successfully. You can now connect with
          teaching assistants, admins, and fellow students on AI Connect.
        </p>
        <p style="color:#555;">Start exploring your courses and joining the community!</p>
        <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
        <p style="color:#bbb;font-size:12px;text-align:center;">
          AI Connect &mdash; El Ryada University Community Platform
        </p>
      </div>
    </div>
    """

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=settings.FROM_EMAIL,
            to_emails=to_email,
            subject="Welcome to AI Connect 🎓",
            html_content=html_body,
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code in (200, 202)
    except Exception as e:
        print(f"[SendGrid] Welcome email failed: {e}")
        return False


def send_password_changed_email(to_email: str, user_name: str) -> bool:
    if not settings.SENDGRID_API_KEY:
        print(f"[DEV EMAIL] Password changed for {to_email} ({user_name})")
        return True

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
      <div style="background:#1565C0;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:24px;">AI Connect</h1>
        <p style="color:#90CAF9;margin:4px 0 0;">Password Changed</p>
      </div>
      <div style="background:#f5f7fa;padding:32px;border-radius:0 0 12px 12px;">
        <p style="color:#333;font-size:16px;">Hi <strong>{user_name}</strong>,</p>
        <p style="color:#555;">
          Your password has been changed successfully.
          If you did not make this change, please contact support immediately.
        </p>
        <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
        <p style="color:#bbb;font-size:12px;text-align:center;">
          AI Connect &mdash; El Ryada University Community Platform
        </p>
      </div>
    </div>
    """

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=settings.FROM_EMAIL,
            to_emails=to_email,
            subject="AI Connect – Password Changed",
            html_content=html_body,
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code in (200, 202)
    except Exception as e:
        print(f"[SendGrid] Password changed email failed: {e}")
        return False
