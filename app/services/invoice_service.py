"""GST tax-invoice PDF generation matching the Dristi Fashions invoice template.

The layout mirrors the reference INV-000001/INV-000002 samples: company
header with the brand logo and "TAX INVOICE" title, invoice/buyer meta, a line
item table that switches between an IGST column (inter-state) and CGST + SGST
columns (intra-state), right-aligned totals with a Balance Due line, amount in
words, notes and an authorized-signature block.

The invoice is built on the fly from the order's stored figures (subtotal,
CGST/SGST/IGST, total) so it always matches what the buyer was charged. The
invoice *number* is the authoritative one recorded on the order's GstInvoice
row at payment time; if a paid order somehow lacks that row we create it here
using the same numbering the payment flow uses, so the number stays stable.
"""

import io
import os
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import gst
from app.core.config import settings
from app.models.order import Order
from app.models.payment import GstInvoice, Payment
from app.services.order_service import _order_gst_breakup

# reportlab is a pure-Python dependency (see requirements.txt).
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Fonts: use a TTF that carries the rupee glyph when one is available (Arial on
# Windows/macOS, DejaVu on Linux) so "₹" renders; otherwise fall back to the
# built-in Helvetica and spell the currency as "Rs.".
# ---------------------------------------------------------------------------
_FONT_REGULAR = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_FONT_BASE = "InvoiceFont"
_CURRENCY = "Rs."

_FONT_CANDIDATES = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
     "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]


def _has_rupee_glyph(path: str) -> bool:
    try:
        from PIL import ImageFont
        font = ImageFont.truetype(path, 20)
        bbox = font.getbbox("₹")
        return bool(bbox and bbox[2] > bbox[0])
    except Exception:
        return False


def _setup_fonts() -> tuple[str, str, str]:
    """Register a rupee-capable TTF if found; return (regular, bold, currency)."""
    global _FONT_REGULAR, _FONT_BOLD, _CURRENCY
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        for regular, bold in _FONT_CANDIDATES:
            if not (os.path.exists(regular) and os.path.exists(bold)):
                continue
            if not (_has_rupee_glyph(regular) and _has_rupee_glyph(bold)):
                continue
            pdfmetrics.registerFont(TTFont(_FONT_BASE, regular))
            pdfmetrics.registerFont(TTFont(_FONT_BASE + "-Bold", bold))
            _FONT_REGULAR = _FONT_BASE
            _FONT_BOLD = _FONT_BASE + "-Bold"
            _CURRENCY = "₹"
            break
    except Exception:
        pass
    return _FONT_REGULAR, _FONT_BOLD, _CURRENCY


_FONT_REGULAR, _FONT_BOLD, _CURRENCY = _setup_fonts()


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


def _plain(value: float) -> str:
    return f"{value:,.2f}"


def _inr(value: float) -> str:
    return f"{_CURRENCY}{value:,.2f}"


def _logo_path() -> str:
    # backend/app/services/invoice_service.py -> backend root
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidate = os.path.join(root, settings.INVOICE_LOGO_PATH.replace("/", os.sep))
    return candidate if os.path.exists(candidate) else None


# ---------------------------------------------------------------------------
# Amount in words (Indian numbering: crore/lakh/thousand).
# ---------------------------------------------------------------------------
_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
         "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
         "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
         "Eighty", "Ninety"]


def _two_digits(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three_digits(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(f"{_ONES[n // 100]} Hundred")
        n %= 100
    if n:
        parts.append(_two_digits(n))
    return " ".join(parts).strip()


def _indian_words(n: int) -> str:
    if n == 0:
        return "Zero"
    parts = []
    crore = n // 10_000_000
    n %= 10_000_000
    lakh = n // 100_000
    n %= 100_000
    thousand = n // 1_000
    n %= 1_000
    if crore:
        parts.append(f"{_indian_words(crore)} Crore")
    if lakh:
        parts.append(f"{_two_digits(lakh)} Lakh")
    if thousand:
        parts.append(f"{_two_digits(thousand)} Thousand")
    if n:
        parts.append(_three_digits(n))
    return " ".join(parts).strip()


def _amount_in_words(amount: float) -> str:
    rupees = int(amount)
    paise = round((amount - rupees) * 100)
    if paise >= 100:
        rupees += paise // 100
        paise %= 100
    words = f"Indian Rupee {_indian_words(rupees)}"
    if paise:
        words += f" and {_two_digits(paise)} Paise"
    return words + " Only"


# ---------------------------------------------------------------------------
# PDF builder
# ---------------------------------------------------------------------------
def build_invoice_pdf(order: Order, invoice: GstInvoice, db: Session) -> bytes:
    """Render the order as a GST tax-invoice PDF matching the reference format."""
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
    base = ParagraphStyle("base", parent=styles["Normal"],
                          fontName=_FONT_REGULAR, fontSize=8, leading=10.5)
    bold = ParagraphStyle("bold", parent=base, fontName=_FONT_BOLD)
    small_bold = ParagraphStyle("small_bold", parent=bold, fontSize=9, leading=12)
    label = ParagraphStyle("label", parent=base)
    value = ParagraphStyle("value", parent=bold)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=44,
        rightMargin=40,
        topMargin=48,
        bottomMargin=48,
        title=invoice.invoice_number,
    )
    story = []

    # --- Header: logo + company block + TAX INVOICE title -------------------
    company_lines = [
        (f"<b>{settings.SELLER_NAME}</b>", 12),
        (f"Company ID : {settings.SELLER_COMPANY_ID}", 8),
        *[(line, 8) for line in settings.SELLER_ADDRESS.splitlines()],
        (f"GSTIN {settings.SELLER_GSTIN}", 8),
        (settings.SELLER_PHONE, 8),
        (settings.SELLER_EMAIL, 8),
    ]
    company_html = "<br/>".join(
        f"<font size=\"{size}\">{line}</font>" for line, size in company_lines
    )
    company_style = ParagraphStyle(
        "company", parent=base, fontSize=8, leading=10.5,
    )

    logo = _logo_path()
    logo_cell = Image(logo, width=112, height=112) if logo else Paragraph("", company_style)

    tax_title = ParagraphStyle(
        "tax_title", parent=styles["Title"], fontName=_FONT_BOLD,
        fontSize=22, leading=26, alignment=TA_RIGHT, textColor=colors.black,
    )
    header = Table(
        [[logo_cell, Paragraph(company_html, company_style),
          Paragraph("TAX INVOICE", tax_title)]],
        colWidths=[124, 230, 157],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header)
    story.append(Spacer(1, 14))

    # --- Invoice / buyer meta ------------------------------------------------
    created = order.created_at.strftime("%d/%m/%Y") if order.created_at else "-"
    place_state = order.shipping_state or "West Bengal"
    place_code = gst.state_gst_code(place_state)
    place_of_supply = f"{place_state} ({place_code})" if place_code else place_state

    meta = Table(
        [
            [Paragraph("#", label), Paragraph(f": {invoice.invoice_number}", value),
             Paragraph("Place Of Supply", label), Paragraph(f": {place_of_supply}", value)],
            [Paragraph("Invoice Date", label), Paragraph(f": {created}", value),
             Paragraph("", label), Paragraph("", value)],
            [Paragraph("Terms", label), Paragraph(": Due on Receipt", value),
             Paragraph("", label), Paragraph("", value)],
            [Paragraph("Due Date", label), Paragraph(f": {created}", value),
             Paragraph("", label), Paragraph("", value)],
        ],
        colWidths=[70, 180, 130, 131],
    )
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(meta)
    story.append(Spacer(1, 12))

    # --- Bill To -------------------------------------------------------------
    bill_lines = ["Bill To", order.user.full_name if order.user else "-"]
    if order.shipping_address:
        bill_lines.extend(order.shipping_address.splitlines())
    bill = Table(
        [[Paragraph("<br/>".join(bill_lines), ParagraphStyle(
            "billto", parent=base, leading=11))]],
        colWidths=[511],
    )
    bill.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(bill)
    story.append(Spacer(1, 16))

    # --- Line items table -----------------------------------------------------
    items = build_line_items_table(order, interstate)
    story.append(items)
    story.append(Spacer(1, 14))

    # --- Totals ---------------------------------------------------------------
    totals_rows = [["Sub Total", _plain(order.subtotal or 0.0)]]
    if (order.discount_amount or 0.0) > 0:
        totals_rows.append(["Discount", "- " + _plain(order.discount_amount)])
    if (getattr(order, "delivery_fee", 0.0) or 0.0) > 0:
        totals_rows.append(["Delivery", _plain(order.delivery_fee)])
    if interstate:
        totals_rows.append(
            [f"IGST{gst.IGST_PERCENTAGE:g} ({gst.IGST_PERCENTAGE:g}%)", _plain(igst)])
    else:
        totals_rows.append(
            [f"CGST{gst.CGST_PERCENTAGE:g} ({gst.CGST_PERCENTAGE:g}%)", _plain(cgst)])
        totals_rows.append(
            [f"SGST{gst.SGST_PERCENTAGE:g} ({gst.SGST_PERCENTAGE:g}%)", _plain(sgst)])
    totals_rows.append(["Total", _inr(order.final_amount or 0.0)])
    totals_rows.append(["Balance Due", _inr(order.final_amount or 0.0)])

    totals = Table(
        [[Paragraph(r[0], bold), Paragraph(r[1], bold)] for r in totals_rows],
        colWidths=[120, 90],
        hAlign="RIGHT",
    )
    last = len(totals_rows) - 1
    balance = last - 1
    totals.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEABOVE", (0, last), (-1, last), 0.6, colors.black),
        ("FONTNAME", (0, last), (-1, last), _FONT_BOLD),
        ("FONTSIZE", (0, balance), (-1, balance), 9),
    ]))
    story.append(totals)
    story.append(Spacer(1, 20))

    # --- Bottom: amount in words / notes  |  authorized signature ------------
    words_style = ParagraphStyle("words", parent=base, leading=11)
    notes_style = ParagraphStyle("notes", parent=base, leading=11)
    signature_style = ParagraphStyle("signature", parent=base, alignment=TA_RIGHT)

    bottom = Table(
        [[
            Paragraph(
                "Total In Words<br/>"
                f"<b>{_amount_in_words(order.final_amount or 0.0)}</b><br/><br/>"
                "Notes<br/>Thanks for your business.",
                ParagraphStyle("bottom_left", parent=base, leading=11),
            ),
            Paragraph("Authorized Signature", signature_style),
        ]],
        colWidths=[300, 211],
    )
    bottom.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(bottom)
    story.append(Spacer(1, 10))

    # Paid via / transaction id, kept as a small footer-style note (only when
    # present on the payment record).
    pay_note = []
    if payment and payment.payment_method:
        pay_note.append(f"Paid via: {payment.payment_method.upper()}")
    if payment and payment.transaction_id:
        pay_note.append(f"Transaction ID: {payment.transaction_id}")
    if pay_note:
        story.append(Paragraph("<br/>".join(pay_note), ParagraphStyle(
            "paynote", parent=base, textColor=colors.HexColor("#888888"))))

    doc.build(story, onFirstPage=_draw_header_footer,
              onLaterPages=_draw_footer)
    return buf.getvalue()


def _draw_header_footer(canvas, doc):
    _draw_footer(canvas, doc)


def _draw_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(_FONT_REGULAR, 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawRightString(A4[0] - 40, 24, str(canvas.getPageNumber()))
    canvas.drawString(44, 24, "POWERED BY")
    canvas.restoreState()


def build_line_items_table(order: Order, interstate: bool) -> Table:
    """Line item table; tax columns switch between IGST and CGST + SGST."""
    gst_rate = gst.IGST_PERCENTAGE if interstate else gst.CGST_PERCENTAGE

    if interstate:
        headers = [["#", "Item & Description", "HSN/SAC", "Qty", "Rate",
                    "IGST", "", "Amount"],
                   ["", "", "", "", "", "%", "Amt", ""]]
        widths = [24, 160, 50, 45, 50, 32, 52, 98]
    else:
        headers = [["#", "Item & Description", "HSN/SAC", "Qty", "Rate",
                    "CGST", "", "SGST", "", "Amount"],
                   ["", "", "", "", "", "%", "Amt", "%", "Amt", ""]]
        widths = [20, 108, 45, 40, 45, 34, 44, 34, 44, 97]

    hdr = ParagraphStyle("hdr", fontName=_FONT_BOLD, fontSize=8, leading=9.5,
                         alignment=1)
    hdr_left = ParagraphStyle("hdr_left", parent=hdr, alignment=0)

    rows = []
    for r in range(2):
        rows.append([Paragraph(c, hdr_left if i < 5 else hdr)
                     for i, c in enumerate(headers[r])])

    for idx, item in enumerate(order.items, start=1):
        line_total = (item.price or 0.0) * (item.quantity or 0)
        tax_amt = line_total * gst_rate / 100
        if interstate:
            data = [
                str(idx),
                Paragraph(item.product_name, ParagraphStyle(
                    "cell", fontName=_FONT_REGULAR, fontSize=8, leading=9.5)),
                settings.DEFAULT_HSN,
                Paragraph(f"{item.quantity}.00<br/>NOS", ParagraphStyle(
                    "qty", fontName=_FONT_REGULAR, fontSize=8, leading=8.5,
                    alignment=1)),
                _plain(item.price or 0.0),
                f"{gst_rate:g}%",
                _plain(tax_amt),
                _plain(line_total),
            ]
        else:
            cgst_amt = line_total * gst.CGST_PERCENTAGE / 100
            sgst_amt = line_total * gst.SGST_PERCENTAGE / 100
            data = [
                str(idx),
                Paragraph(item.product_name, ParagraphStyle(
                    "cell", fontName=_FONT_REGULAR, fontSize=8, leading=9.5)),
                settings.DEFAULT_HSN,
                Paragraph(f"{item.quantity}.00<br/>NOS", ParagraphStyle(
                    "qty", fontName=_FONT_REGULAR, fontSize=8, leading=8.5,
                    alignment=1)),
                _plain(item.price or 0.0),
                f"{gst.CGST_PERCENTAGE:g}%",
                _plain(cgst_amt),
                f"{gst.SGST_PERCENTAGE:g}%",
                _plain(sgst_amt),
                _plain(line_total),
            ]
        rows.append(data)

    table = Table(rows, colWidths=widths, repeatRows=2)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#f2f0f7")),
        ("TEXTCOLOR", (0, 0), (-1, 1), colors.black),
        ("FONTNAME", (0, 0), (-1, 1), _FONT_BOLD),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 2), (-1, -1),
         [colors.white, colors.HexColor("#fbf9fd")]),
    ]
    # SPAN commands so tax names cover their % / Amt sub-columns in the header.
    for (r1, c1, r2, c2) in _header_spans(interstate):
        style_cmds.append(("SPAN", (c1, r1), (c2, r2)))
    table.setStyle(TableStyle(style_cmds))
    return table


def _header_spans(interstate: bool):
    if interstate:
        return [(0, 0, 0, 1), (1, 0, 1, 1), (2, 0, 2, 1), (3, 0, 3, 1),
                (4, 0, 4, 1), (5, 0, 6, 0), (7, 0, 7, 1)]
    return [(0, 0, 0, 1), (1, 0, 1, 1), (2, 0, 2, 1), (3, 0, 3, 1),
            (4, 0, 4, 1), (5, 0, 6, 0), (7, 0, 8, 0), (9, 0, 9, 1)]


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
