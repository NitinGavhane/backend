import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings


def send_email(recipient: str, subject: str, body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = recipient
    msg["Subject"] = subject

    part = MIMEText(body, "html")
    msg.attach(part)

    ctx = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls(context=ctx)
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, recipient, msg.as_string())


def send_otp_email(recipient: str, otp: str) -> None:
    subject = "Your OTP Code — Garment E-commerce"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px;">
        <div style="max-width: 480px; margin: auto; background: white; border-radius: 8px; padding: 32px;">
            <h2 style="color: #333; margin-top: 0;">Email Verification</h2>
            <p style="color: #555; font-size: 15px;">Your one-time verification code is:</p>
            <div style="text-align: center; margin: 24px 0;">
                <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #1a73e8;">{otp}</span>
            </div>
            <p style="color: #888; font-size: 13px;">This code is valid for <strong>10 minutes</strong>. Do not share it with anyone.</p>
            <hr style="border: none; border-top: 1px solid #eee;">
            <p style="color: #aaa; font-size: 12px;">Garment E-commerce Platform</p>
        </div>
    </body>
    </html>
    """
    send_email(recipient, subject, body)


def send_password_reset_email(recipient: str, otp: str) -> None:
    subject = "Password Reset OTP — Garment E-commerce"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px;">
        <div style="max-width: 480px; margin: auto; background: white; border-radius: 8px; padding: 32px;">
            <h2 style="color: #333; margin-top: 0;">Password Reset</h2>
            <p style="color: #555; font-size: 15px;">Use the code below to reset your password:</p>
            <div style="text-align: center; margin: 24px 0;">
                <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #d93025;">{otp}</span>
            </div>
            <p style="color: #888; font-size: 13px;">This code is valid for <strong>10 minutes</strong>. If you did not request this, ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #eee;">
            <p style="color: #aaa; font-size: 12px;">Garment E-commerce Platform</p>
        </div>
    </body>
    </html>
    """
    send_email(recipient, subject, body)
