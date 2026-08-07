import logging
import smtplib
import ssl
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate

from app.core.config import settings

logger = logging.getLogger(__name__)

SENDING_DOMAIN = settings.SMTP_FROM_EMAIL.split("@")[1]
SENDER_NAME = "Dristi Fashions"


def _ses_client():
    """Build a boto3 SES client using the configured credentials.

    Picks up explicit keys from settings if supplied; otherwise falls back to
    the standard boto3 credential chain (EC2 instance role / env vars), which is
    the same path S3 uploads already rely on.
    """
    import boto3

    kwargs = {"region_name": settings.SES_REGION}
    if settings.SES_ACCESS_KEY_ID and settings.SES_SECRET_ACCESS_KEY:
        kwargs.update(
            aws_access_key_id=settings.SES_ACCESS_KEY_ID,
            aws_secret_access_key=settings.SES_SECRET_ACCESS_KEY,
        )
    return boto3.client("ses", **kwargs)


def _send_via_ses_api(recipient: str, subject: str, html_body: str, text_body: str) -> None:
    """Send through the AWS SES SendEmail API (boto3)."""
    params = {
        "Source": f"{SENDER_NAME} <{settings.SMTP_FROM_EMAIL}>",
        "Destination": {"ToAddresses": [recipient]},
        "Message": {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html_body, "Charset": "UTF-8"},
                "Text": {"Data": text_body, "Charset": "UTF-8"},
            },
        },
        "ReplyToAddresses": [settings.SMTP_FROM_EMAIL],
    }
    if settings.SES_CONFIGURATION_SET:
        params["ConfigurationSetName"] = settings.SES_CONFIGURATION_SET

    client = _ses_client()
    client.send_email(**params)


def _build_smtp_message(recipient: str, subject: str, html_body: str, text_body: str) -> str:
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((SENDER_NAME, settings.SMTP_FROM_EMAIL))
    msg["Reply-To"] = settings.SMTP_FROM_EMAIL
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Message-ID"] = f"<{uuid.uuid4().hex}@{SENDING_DOMAIN}>"
    msg["Date"] = formatdate(timeval=None, localtime=True)
    msg["List-Unsubscribe"] = f"<mailto:unsubscribe@{SENDING_DOMAIN}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg["Precedence"] = "bulk"
    msg["X-Mailer"] = "DristiFashions-Mailer/1.0"
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg.as_string()


def _send_via_smtp(recipient: str, subject: str, html_body: str, text_body: str) -> None:
    message = _build_smtp_message(recipient, subject, html_body, text_body)
    ctx = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls(context=ctx)
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, recipient, message)


def send_email(recipient: str, subject: str, html_body: str, text_body: str = "") -> None:
    if recipient is None or not recipient.strip():
        raise ValueError("Cannot send an email with no recipient")

    if not text_body:
        text_body = f"Your OTP code is: {html_body}"

    primary = settings.EMAIL_BACKEND.lower()
    order = ("ses", "smtp") if primary == "ses" else ("smtp", "ses")

    errors = []
    for backend in order:
        try:
            if backend == "ses":
                _send_via_ses_api(recipient, subject, html_body, text_body)
            else:
                _send_via_smtp(recipient, subject, html_body, text_body)
            return
        except Exception as exc:  # noqa: BLE001 - cross-transport fallback is intentional
            errors.append(f"{backend}: {exc}")
            logger.warning("email backend '%s' failed (%s); trying fallback", backend, exc)

    # raise the primary backend's error so callers surface the root cause
    first_backend, _ = order
    primary_error = errors[0] if errors else "no transports available"
    raise RuntimeError(f"All email transports failed for {recipient} [{primary_error}]")


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


def _wrap_otp_into_card(title: str, subtitle: str, body_html: str, accent_color: str = "#0d1648") -> str:
    """A reusable transactional card (not an OTP box) for order/return updates."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#f4f4f6">
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#f4f4f6;padding:24px 0">
<tr><td align="center">
<table role="presentation" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%">
<tr><td style="background:#ffffff;border-radius:12px;padding:40px 32px">
<h1 style="margin:0 0 8px;font-size:22px;color:#1a1a2e;font-weight:600">{title}</h1>
<p style="margin:0 0 24px;font-size:15px;color:#555566;line-height:1.5">{subtitle}</p>
{body_html}
<p style="margin:24px 0 0;font-size:13px;color:#888899;line-height:1.6">Questions? Reply to this email or reach us at {settings.SELLER_EMAIL}.</p>
</td></tr>
<tr><td style="padding:24px 0 0;text-align:center">
<p style="margin:0;font-size:12px;color:#aaaabb">Dristi Fashions</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _order_otp_box(otp: str) -> str:
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 24px">
<tr><td style="background:#f8f9fa;border-radius:8px;padding:16px 32px;letter-spacing:10px;font-size:36px;font-weight:700;color:#0d1648;text-align:center;font-family:Menlo,Monaco,monospace" role="heading" aria-level="2">{otp}</td></tr>
</table>
<p style="margin:0 0 4px;font-size:13px;color:#888899">Share this code only with the person who arrives with your parcel / at the pickup. It expires in <strong>10 minutes</strong>.</p>"""


def send_order_confirmation_email(recipient: str, order_number: str, items_summary: str, total: float, estimated_delivery) -> None:
    subject = f"Order Confirmed – {order_number}"
    body = f"""
<p style="margin:0 0 16px;font-size:14px;color:#46464f;line-height:1.6">Thank you for your order! We have received it and will start packing it shortly.</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:#f8f9fa;border-radius:8px;padding:16px">
<tr><td style="font-size:13px;color:#555566;line-height:1.7">
<strong style="color:#1a1a2e">Order number:</strong> {order_number}<br/>
<strong style="color:#1a1a2e">Items:</strong> {items_summary}<br/>
<strong style="color:#1a1a2e">Total:</strong> ₹{total:.2f}<br/>
{f"<strong style='color:#1a1a2e'>Estimated delivery:</strong> {estimated_delivery.strftime('%d %b %Y')}<br/>" if estimated_delivery else ""}
</td></tr>
</table>
"""
    html = _wrap_otp_into_card("Order Confirmed", f"Order {order_number} is being prepared.", body, "#1e6b32")
    text = f"Your order {order_number} has been confirmed. Total: ₹{total:.2f}."
    send_email(recipient, subject, html, text)


def send_dispatch_otp_email(recipient: str, order_number: str, otp: str) -> None:
    subject = f"Your Order is Out for Delivery – {order_number}"
    body = f"""
<p style="margin:0 0 20px;font-size:14px;color:#46464f;line-height:1.6">Your order <strong>{order_number}</strong> has been dispatched. When the delivery partner arrives, share the code below to confirm delivery:</p>
{_order_otp_box(otp)}
"""
    html = _wrap_otp_into_card("Order Dispatched", f"Order {order_number} is on its way.", body, "#14538f")
    text = f"Your order {order_number} is dispatched. Delivery OTP: {otp}. Share it only with the delivery partner."
    send_email(recipient, subject, html, text)


def send_order_delivered_email(recipient: str, order_number: str) -> None:
    subject = f"Delivered – {order_number}"
    body = f"""
<p style="margin:0 0 8px;font-size:14px;color:#46464f;line-height:1.6">Great news! Your order <strong>{order_number}</strong> has been delivered. We hope you love it.</p>
<p style="margin:0;font-size:14px;color:#46464f;line-height:1.6">Changed your mind? Delivered orders can be returned or replaced within the return window from the app or website.</p>
"""
    html = _wrap_otp_into_card("Order Delivered", f"Order {order_number} is with you now.", body, "#1e6b32")
    text = f"Your order {order_number} has been delivered. You can request a return or replacement if needed."
    send_email(recipient, subject, html, text)


def send_return_requested_email(recipient: str, order_number: str) -> None:
    subject = f"Return Request Received – {order_number}"
    body = f"""
<p style="margin:0;font-size:14px;color:#46464f;line-height:1.6">We received your return request for order <strong>{order_number}</strong>. Our team will review it shortly and email you once it is approved or needs more information.</p>
"""
    html = _wrap_otp_into_card("Return Request Received", f"Order {order_number}", body, "#14538f")
    text = f"We received your return request for order {order_number}. Our team will review it shortly."
    send_email(recipient, subject, html, text)


def send_return_approved_email(recipient: str, order_number: str, otp: str) -> None:
    subject = f"Return Approved – {order_number}"
    body = f"""
<p style="margin:0 0 16px;font-size:14px;color:#46464f;line-height:1.6">Your return request for order <strong>{order_number}</strong> has been approved. Our pickup partner will arrive soon — share this code to complete the pickup:</p>
{_order_otp_box(otp)}
"""
    html = _wrap_otp_into_card("Return Approved", f"Order {order_number} is approved for pickup.", body, "#1e6b32")
    text = f"Return approved for order {order_number}. Pickup OTP: {otp}. Share it only with the pickup partner."
    send_email(recipient, subject, html, text)


def send_return_rejected_email(recipient: str, order_number: str, reason: str) -> None:
    subject = f"Return Update – {order_number}"
    body = f"""
<p style="margin:0 0 12px;font-size:14px;color:#46464f;line-height:1.6">We reviewed your return request for order <strong>{order_number}</strong> and are unable to accept it.</p>
<p style="margin:0;font-size:14px;color:#46464f;line-height:1.6;background:#fdeaea;border-radius:8px;padding:12px"><strong style="color:#ba1a1a">Reason:</strong> {reason}</p>
<p style="margin:16px 0 0;font-size:13px;color:#888899">If you believe this is a mistake, reply to this email and we will take another look.</p>
"""
    html = _wrap_otp_into_card("Return Not Accepted", f"Order {order_number}", body, "#ba1a1a")
    text = f"Your return request for order {order_number} was not accepted. Reason: {reason}"
    send_email(recipient, subject, html, text)


def send_return_picked_up_email(recipient: str, order_number: str) -> None:
    subject = f"Pickup Complete – {order_number}"
    body = f"""
<p style="margin:0;font-size:14px;color:#46464f;line-height:1.6">The return pickup for order <strong>{order_number}</strong> is complete. We will process your refund once the returned item passes our quality check — typically within 5–7 business days.</p>
"""
    html = _wrap_otp_into_card("Return Pickup Complete", f"Order {order_number}", body, "#1e6b32")
    text = f"Return pickup for order {order_number} is complete. Refund will follow the quality check."
    send_email(recipient, subject, html, text)
