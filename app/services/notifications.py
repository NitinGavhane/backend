import logging

from app.services import email_service
from app.core.config import settings

logger = logging.getLogger(__name__)

# WhatsApp is currently an opt-in stub. A provider (Twilio / Meta Cloud API /
# Gupshup / Interakt) plugs in here without touching the call sites — the
# delivery/return workflow only ever calls send_whatsapp_message().
WHATSAPP_PROVIDER = settings.WHATSAPP_PROVIDER


def _wa_target(phone: str | None) -> str | None:
    """Normalise a phone number for WhatsApp (E.164, no '+'). None when absent."""
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    return digits


def send_whatsapp_message(phone: str | None, template: str, variables: dict) -> None:
    """Send a WhatsApp template message to a customer.

    No-op (logged) until a provider is configured via WHATSAPP_PROVIDER. Each
    provider has its own template-name + payload convention, so this function
    is the only seam that has to know about them.
    """
    target = _wa_target(phone)
    if not target:
        logger.info("whatsapp skipped: no phone for template=%s", template)
        return
    if not WHATSAPP_PROVIDER:
        logger.info(
            "whatsapp stub (provider not configured): template=%s phone=%s vars=%s",
            template,
            target,
            variables,
        )
        return

    if WHATSAPP_PROVIDER == "twilio":
        _send_twilio(target, template, variables)
    else:
        logger.warning("whatsapp provider '%s' not implemented; dropping message", WHATSAPP_PROVIDER)


def _send_twilio(target: str, template: str, variables: dict) -> None:
    """Twilio Content API — content_sid is the approved template's SID."""
    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=f"whatsapp:{settings.TWILIO_WHATSAPP_FROM}",
            to=f"whatsapp:{target}",
            content_sid=settings.TWILIO_TEMPLATES.get(template),
            content_variables=variables,
        )
    except Exception:
        logger.exception("failed to send WhatsApp template=%s phone=%s", template, target)


# ── Workflow-level senders ──────────────────────────────────────────────────
#
# Each event fans out across every configured channel (email today, WhatsApp
# when a provider is enabled). Call sites import these, never the low-level
# senders, so adding a channel is a one-line change in one file.


def notify_order_placed(order) -> None:
    """Order placed confirmation (paid at checkout, or payment pending)."""
    items_summary = ", ".join(f"{i.product_name} x{i.quantity}" for i in order.items)
    try:
        email_service.send_order_confirmation_email(
            order.user.email,
            order.order_number,
            items_summary,
            order.final_amount,
            order.estimated_delivery,
        )
    except Exception:
        logger.exception("failed to email order confirmation for %s", order.order_number)
    send_whatsapp_message(
        order.user.phone,
        "order_placed",
        {"1": order.order_number, "2": f"Rs. {order.final_amount:.2f}"},
    )


def notify_order_dispatched(order) -> None:
    """Order dispatched — includes the delivery OTP the customer reads out."""
    try:
        email_service.send_dispatch_otp_email(order.user.email, order.order_number, order.dispatch_otp)
    except Exception:
        logger.exception("failed to email dispatch OTP for %s", order.order_number)
    send_whatsapp_message(
        order.user.phone,
        "order_dispatched",
        {"1": order.order_number, "2": order.dispatch_otp},
    )


def notify_order_delivered(order) -> None:
    try:
        email_service.send_order_delivered_email(order.user.email, order.order_number)
    except Exception:
        logger.exception("failed to email delivery confirmation for %s", order.order_number)
    send_whatsapp_message(order.user.phone, "order_delivered", {"1": order.order_number})


def notify_order_cancelled(order, reason: str) -> None:
    """Order cancelled — customer-initiated, store-initiated, or auto-expired."""
    try:
        email_service.send_order_cancelled_email(order.user.email, order.order_number, reason)
    except Exception:
        logger.exception("failed to email cancellation notice for %s", order.order_number)
    send_whatsapp_message(order.user.phone, "order_cancelled", {"1": order.order_number})


def notify_return_requested(order) -> None:
    """Confirmation that a return/replace request is under review."""
    try:
        email_service.send_return_requested_email(order.user.email, order.order_number)
    except Exception:
        logger.exception("failed to email return confirmation for %s", order.order_number)
    send_whatsapp_message(order.user.phone, "return_requested", {"1": order.order_number})


def notify_return_approved(order) -> None:
    """Return/replace approved — includes the pickup OTP."""
    try:
        email_service.send_return_approved_email(order.user.email, order.order_number, order.return_otp)
    except Exception:
        logger.exception("failed to email return-approval OTP for %s", order.order_number)
    send_whatsapp_message(order.user.phone, "return_approved", {"1": order.order_number, "2": order.return_otp})


def notify_return_rejected(order, reason: str) -> None:
    try:
        email_service.send_return_rejected_email(order.user.email, order.order_number, reason)
    except Exception:
        logger.exception("failed to email return rejection for %s", order.order_number)
    send_whatsapp_message(order.user.phone, "return_rejected", {"1": order.order_number})


def notify_return_picked_up(order) -> None:
    try:
        email_service.send_return_picked_up_email(order.user.email, order.order_number)
    except Exception:
        logger.exception("failed to email return pickup confirmation for %s", order.order_number)
    send_whatsapp_message(order.user.phone, "return_picked_up", {"1": order.order_number})
