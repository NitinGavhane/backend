"""GST tax-invoice PDF generation.

The invoice is built on the fly from the order's stored figures (subtotal,
CGST/SGST/IGST, total) so it always matches what the buyer was charged. The
invoice *number* is the authoritative one recorded on the order's GstInvoice
row at payment time; if a paid order somehow lacks that row we create it here
using the same numbering the payment flow uses, so the number stays stable.
"""

import io
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.order import Order
from app.models.payment import GstInvoice, Payment
from app.services.order_service import _order_gst_breakup

# reportlab is a pure-Python dependency (see requirements.txt).
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def _invoice_number_for(order: Order) -> str:
    """The same numbering payment_service.verify_payment uses."""
    return f"INV-{order.order_number}-{str(order.id)[:8].upper()}"


def get_or_create_invoice(order: Order, db: Session) -> GstInvoice:
    invoice = db.query(GstInvoice).filter(GstInvoice.order_id == order.id).first()
    if invoice:
        return invoice
    invoice = GstInvoice(
        order_id=order.id,
        invoice_number=_invoice_number_for(order),
        gst_number=settings.SELLER_GSTIN,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def _money(value: float) -> str:
    return f"Rs. {value:,.2f}"


def build_invoice_pdf(order: Order, invoice: GstInvoice, db: Session) -> bytes:
    """Render the order as a GST tax-invoice PDF and return the bytes."""
    breakup = _order_gst_breakup(order)
    cgst = breakup["cgst_amount"]
    sgst = breakup["sgst_amount"]
    igst = breakup["igst_amount"]
    interstate = igst > 0

    payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .order_by(Payment.created_at.desc())
        .first()
    )

    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9, leading=12)
    right = ParagraphStyle("right", parent=small, alignment=2)
    h_title = ParagraphStyle(
        "h_title", parent=styles["Title"], fontSize=18, spaceAfter=2
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=invoice.invoice_number,
    )
    story = []

    # Header: seller identity + "Tax Invoice" label.
    header = Table(
        [
            [
                Paragraph(f"<b>{settings.SELLER_NAME}</b><br/>"
                          f"{settings.SELLER_ADDRESS}<br/>"
                          f"GSTIN: {settings.SELLER_GSTIN}<br/>"
                          f"{settings.SELLER_EMAIL}", small),
                Paragraph("<b>TAX INVOICE</b>", ParagraphStyle(
                    "inv", parent=h_title, alignment=2)),
            ]
        ],
        colWidths=[95 * mm, 79 * mm],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(header)
    story.append(Spacer(1, 8))

    # Invoice / buyer meta.
    created = order.created_at.strftime("%d %b %Y") if order.created_at else "-"
    buyer_name = order.user.full_name if order.user else "-"
    ship_to = (order.shipping_address or "-").replace("\n", "<br/>")
    meta = Table(
        [
            [
                Paragraph(
                    f"<b>Invoice No:</b> {invoice.invoice_number}<br/>"
                    f"<b>Order No:</b> {order.order_number}<br/>"
                    f"<b>Invoice Date:</b> {created}<br/>"
                    f"<b>Payment Status:</b> {order.payment_status.upper()}",
                    small,
                ),
                Paragraph(
                    f"<b>Bill / Ship To:</b><br/>{buyer_name}<br/>{ship_to}",
                    small,
                ),
            ]
        ],
        colWidths=[87 * mm, 87 * mm],
    )
    meta.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta)
    story.append(Spacer(1, 12))

    # Line items.
    rows = [["#", "Item", "Qty", "Unit Price", "Amount"]]
    for idx, item in enumerate(order.items, start=1):
        line_total = (item.price or 0.0) * (item.quantity or 0)
        rows.append(
            [
                str(idx),
                Paragraph(item.product_name, small),
                str(item.quantity),
                _money(item.price or 0.0),
                _money(line_total),
            ]
        )
    items_table = Table(
        rows, colWidths=[10 * mm, 88 * mm, 16 * mm, 30 * mm, 30 * mm]
    )
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7b1fa2")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#f6f2f8")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 10))

    # Totals block, right-aligned.
    totals_rows = [["Subtotal", _money(order.subtotal or 0.0)]]
    if (order.discount_amount or 0.0) > 0:
        totals_rows.append(["Discount", "- " + _money(order.discount_amount)])
    if interstate:
        totals_rows.append(["IGST", _money(igst)])
    else:
        totals_rows.append(["CGST", _money(cgst)])
        totals_rows.append(["SGST", _money(sgst)])
    if (getattr(order, "delivery_fee", 0.0) or 0.0) > 0:
        totals_rows.append(["Delivery", _money(order.delivery_fee)])
    totals_rows.append(["Total", _money(order.final_amount or 0.0)])

    totals = Table(totals_rows, colWidths=[40 * mm, 40 * mm], hAlign="RIGHT")
    last = len(totals_rows) - 1
    totals.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, last), (-1, last), 0.8, colors.HexColor("#7b1fa2")),
                ("FONTNAME", (0, last), (-1, last), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(totals)
    story.append(Spacer(1, 18))

    if payment and payment.payment_method:
        story.append(
            Paragraph(f"Paid via: {payment.payment_method.upper()}", small)
        )
    if payment and payment.transaction_id:
        story.append(
            Paragraph(f"Transaction ID: {payment.transaction_id}", small)
        )
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "This is a computer-generated invoice and does not require a "
            "signature.",
            ParagraphStyle("footer", parent=small, textColor=colors.HexColor("#888888")),
        )
    )

    doc.build(story)
    return buf.getvalue()


def generate_invoice_pdf(order_id: str, user_id, db: Session) -> tuple[bytes, str]:
    """Load a user's paid order and return (pdf_bytes, filename).

    Scoped to the owner so one buyer cannot pull another's invoice; a foreign
    or missing order is reported as 404, matching the payments endpoints.
    """
    try:
        oid = uuid.UUID(str(order_id))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid order_id")
    order = (
        db.query(Order)
        .filter(Order.id == oid, Order.user_id == user_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.payment_status != "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is available only after the order is paid",
        )

    invoice = get_or_create_invoice(order, db)
    pdf = build_invoice_pdf(order, invoice, db)
    filename = f"{invoice.invoice_number}.pdf"
    return pdf, filename
