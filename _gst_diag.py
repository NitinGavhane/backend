import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
from sqlalchemy import text
from app.core.database import SessionLocal
from app.core import gst

db = SessionLocal()
rows = db.execute(text(
    "SELECT order_number, shipping_state, subtotal, gst_amount, cgst_amount, "
    "sgst_amount, igst_amount, delivery_fee, final_amount, created_at "
    "FROM orders ORDER BY created_at"
)).fetchall()
print(f"{'order_number':<24}{'state':<28}{'intra?':<7}{'cgst':>6}{'sgst':>6}{'igst':>6}{'gst':>7}  created")
for r in rows:
    intra = gst.is_intra_state(r.shipping_state)
    # label mismatch: intra order should carry cgst/sgst (not igst); inter should carry igst only
    label_mismatch = False
    if intra and (r.igst_amount or 0) > 0.01:
        label_mismatch = True
    if (not intra) and ((r.cgst_amount or 0) > 0.01 or (r.sgst_amount or 0) > 0.01):
        label_mismatch = True
    mark = "  <-- MISMATCH" if label_mismatch else ""
    state = (r.shipping_state or "")[:27]
    print(f"{r.order_number:<24}{state:<28}{str(intra):<7}{r.cgst_amount or 0:>6}{r.sgst_amount or 0:>6}{r.igst_amount or 0:>6}{r.gst_amount or 0:>7}  {str(r.created_at)[:19]}{mark}")
db.close()