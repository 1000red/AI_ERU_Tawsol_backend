from app.core.config import settings


def send_otp_email(to_email: str, otp: str, user_name: str) -> bool:
    if not settings.SENDGRID_API_KEY:
        print(f"[DEV EMAIL] OTP for {to_email} ({user_name}): {otp}")
        return True

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
      <div style="background:#1565C0;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:24px;">ERU Tawasol</h1>
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
          ERU Tawasol &mdash; El Ryada University Community Platform
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
            subject="ERU Tawasol – Your Password Reset Code",
            html_content=html_body,
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code in (200, 202)
    except Exception as e:
        print(f"[SendGrid] Failed to send email to {to_email}: {e}")
        return False


def send_welcome_email(to_email: str, user_name: str) -> bool:
    if not settings.SENDGRID_API_KEY:
        print(f"[DEV EMAIL] Welcome email for {to_email} ({user_name})")
        return True

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
      <div style="background:#1565C0;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;">Welcome to ERU Tawasol!</h1>
      </div>
      <div style="background:#f5f7fa;padding:32px;border-radius:0 0 12px 12px;">
        <p style="color:#333;font-size:16px;">Hi <strong>{user_name}</strong>,</p>
        <p style="color:#555;">
          Your account has been created successfully. You can now connect with
          professors, teaching assistants, and fellow students on ERU Tawasol.
        </p>
        <p style="color:#555;">Start exploring your courses and joining the community!</p>
      </div>
    </div>
    """

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=settings.FROM_EMAIL,
            to_emails=to_email,
            subject="Welcome to ERU Tawasol 🎓",
            html_content=html_body,
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code in (200, 202)
    except Exception as e:
        print(f"[SendGrid] Welcome email failed: {e}")
        return False


def send_temp_password_email(to_email: str, user_name: str, temp_password: str) -> bool:
    if not settings.SENDGRID_API_KEY:
        print(f"[DEV EMAIL] Temp password for {to_email} ({user_name}): {temp_password}")
        return True

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
      <div style="background:#1565C0;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:24px;">ERU Tawasol</h1>
        <p style="color:#90CAF9;margin:4px 0 0;">Your Account is Ready</p>
      </div>
      <div style="background:#f5f7fa;padding:32px;border-radius:0 0 12px 12px;">
        <p style="color:#333;font-size:16px;">Hi <strong>{user_name}</strong>,</p>
        <p style="color:#555;">
          Your account has been created. Use the temporary password below to log in,
          then change it immediately from your profile.
        </p>
        <div style="background:#fff;border:2px dashed #1565C0;border-radius:12px;
                    text-align:center;padding:24px;margin:24px 0;">
          <p style="color:#999;font-size:13px;margin:0 0 8px;">Temporary Password</p>
          <span style="font-size:28px;font-weight:bold;color:#1565C0;
                       font-family:monospace;letter-spacing:4px;">{temp_password}</span>
        </div>
        <p style="color:#e53935;font-size:13px;">
          ⚠️ Please change your password immediately after logging in.
        </p>
        <hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0;">
        <p style="color:#bbb;font-size:12px;text-align:center;">
          ERU Tawasol &mdash; El Ryada University Community Platform
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
            subject="ERU Tawasol – Your Temporary Password",
            html_content=html_body,
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code in (200, 202)
    except Exception as e:
        print(f"[SendGrid] Temp password email failed: {e}")
        return False