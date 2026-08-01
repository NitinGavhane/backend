import smtplib
import ssl
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate

from app.core.config import settings

SENDING_DOMAIN = settings.SMTP_FROM_EMAIL.split("@")[1]


def send_email(recipient: str, subject: str, html_body: str, text_body: str = "") -> None:
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr(("Dristi Fashions", settings.SMTP_FROM_EMAIL))
    msg["Reply-To"] = settings.SMTP_FROM_EMAIL
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Message-ID"] = f"<{uuid.uuid4().hex}@{SENDING_DOMAIN}>"
    msg["Date"] = formatdate(timeval=None, localtime=True)
    msg["List-Unsubscribe"] = f"<mailto:unsubscribe@{SENDING_DOMAIN}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg["Precedence"] = "bulk"
    msg["X-Mailer"] = "DristiFashions-Mailer/1.0"

    if not text_body:
        text_body = f"Your OTP code is: {html_body}"

    text_part = MIMEText(text_body, "plain")
    html_part = MIMEText(html_body, "html")
    msg.attach(text_part)
    msg.attach(html_part)

    ctx = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls(context=ctx)
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, recipient, msg.as_string())


def _build_otp_html(title: str, otp: str, subtitle: str, accent_color: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#f4f4f6">
<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;overflow:hidden;opacity:0">Use code {otp} to complete your request on Dristi Fashions.</div>
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#f4f4f6;padding:24px 0">
<tr><td align="center">
<table role="presentation" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%">
<tr><td style="background:#ffffff;border-radius:12px;padding:40px 32px">
<h1 style="margin:0 0 8px;font-size:22px;color:#1a1a2e;font-weight:600">{title}</h1>
<p style="margin:0 0 24px;font-size:15px;color:#555566;line-height:1.5">{subtitle}</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 24px">
<tr><td style="background:#f8f9fa;border-radius:8px;padding:16px 32px;letter-spacing:10px;font-size:36px;font-weight:700;color:{accent_color};text-align:center;font-family:Menlo,Monaco,monospace" role="heading" aria-level="2">{otp}</td></tr>
</table>
<p style="margin:0 0 4px;font-size:13px;color:#888899">This code expires in <strong>10 minutes</strong>. Never share it with anyone.</p>
<p style="margin:0;font-size:13px;color:#888899">If you did not request this, you can safely ignore this email.</p>
</td></tr>
<tr><td style="padding:24px 0 0;text-align:center">
<p style="margin:0;font-size:12px;color:#aaaabb">Dristi Fashions</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def send_otp_email(recipient: str, otp: str, context: str = "verification") -> None:
    if context == "login":
        subject = "Login OTP – Dristi Fashions"
        html = _build_otp_html("Sign In", otp, "Use the code below to sign in to your account.", "#2563eb")
        text = f"Your login code is: {otp}\n\nThis code expires in 10 minutes. Never share it with anyone."
    else:
        subject = "Your OTP Code – Dristi Fashions"
        html = _build_otp_html("Email Verification", otp, "Use the code below to verify your email address.", "#2563eb")
        text = f"Your email verification code is: {otp}\n\nThis code expires in 10 minutes. Never share it with anyone."
    send_email(recipient, subject, html, text)


def send_password_reset_email(recipient: str, otp: str) -> None:
    subject = "Password Reset OTP – Dristi Fashions"
    html = _build_otp_html("Reset Your Password", otp, "Use the code below to reset your password.", "#dc2626")
    text = f"Your password reset code is: {otp}\n\nThis code expires in 10 minutes. Never share it with anyone."
    send_email(recipient, subject, html, text)
