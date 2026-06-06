import subprocess, webbrowser, tempfile, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from app.core.database import SessionLocal
from app.models.user import User
from app.models.product import Product, ProductVariant, ProductImage
from app.models.category import Category
from app.models.order import Order, OrderItem
from app.models.cart import CartItem
from app.models.wallet import WalletTransaction
from app.models.referral import ReferralEarning
from app.models.payment import Payment

db = SessionLocal()

HTML = """
<html><head><meta charset="utf-8">
<title>Database Viewer</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:#0f1117;color:#e4e7ed;padding:32px}
h1{color:#00e5a0;font-size:28px;margin-bottom:8px}
.sub{color:#888;margin-bottom:32px}
h2{color:#4f8eff;margin:28px 0 12px;font-size:20px;border-bottom:1px solid #2a2d35;padding-bottom:6px}
table{width:100%;border-collapse:collapse;margin-bottom:8px;font-size:13px}
th{background:#1a1d26;color:#888;text-align:left;padding:8px 10px;font-weight:500;text-transform:uppercase;font-size:11px;letter-spacing:.05em}
td{padding:7px 10px;border-bottom:1px solid #1e212a}
tr:hover td{background:#1a1d26}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:500}
.badge-customer{background:#1a3a2a;color:#00e5a0}
.badge-admin{background:#3a1a2a;color:#ff6b6b}
.badge-true{background:#1a3a2a;color:#00e5a0}
.badge-false{background:#3a2a1a;color:#ffb547}
.num{text-align:right;font-variant-numeric:tabular-nums}
</style></head><body>
<h1>Database Viewer</h1>
<p class="sub">PostgreSQL — garment_ecommerce</p>
"""

def get_table(title, cols, rows):
    h = "".join(f"<th>{c}</th>" for c in cols)
    r = "".join("<tr>" + "".join(f"<td{' class=num' if isinstance(v, (int,float)) else ''}>{v}</td>" for v in row) + "</tr>" for row in rows)
    return f"<h2>{title} ({len(rows)})</h2><table><thead><tr>{h}</tr></thead><tbody>{r}</tbody></table>"

# ── Users ──
cols = ["ID (short)", "Full Name", "Email", "Phone", "Role", "Referral Code", "Wallet", "Verified"]
rows = []
for u in db.query(User).order_by(User.created_at.desc()).all():
    badge_role = f"<span class='badge badge-{u.role}'>{u.role}</span>"
    badge_v = f"<span class='badge badge-{str(u.is_verified).lower()}'>{u.is_verified}</span>"
    rows.append((str(u.id)[:8]+"..", u.full_name, u.email, u.phone or "—", badge_role, u.referral_code or "—", f"${u.wallet_balance:.2f}", badge_v))
HTML += get_table("Users", cols, rows)

# ── Categories ──
cols = ["ID (short)", "Name", "Slug", "Active"]
rows = []
for c in db.query(Category).order_by(Category.created_at.desc()).all():
    rows.append((str(c.id)[:8]+"..", c.name, c.slug, f"<span class='badge badge-{str(c.is_active).lower()}'>{c.is_active}</span>"))
HTML += get_table("Categories", cols, rows)

# ── Products ──
cols = ["ID (short)", "Title", "SKU", "Price", "Discount", "GST%", "Stock", "Active"]
rows = []
for p in db.query(Product).order_by(Product.created_at.desc()).all():
    rows.append((str(p.id)[:8]+"..", p.title, p.sku, f"${p.price:.2f}", f"${p.discount_price:.2f}" if p.discount_price else "—", f"{p.gst_percentage}%", p.stock, f"<span class='badge badge-{str(p.is_active).lower()}'>{p.is_active}</span>"))
HTML += get_table("Products", cols, rows)

# ── Orders ──
cols = ["ID (short)", "Order #", "User ID", "Subtotal", "GST", "Final", "Status", "Payment"]
rows = []
for o in db.query(Order).order_by(Order.created_at.desc()).all():
    rows.append((str(o.id)[:8]+"..", o.order_number, str(o.user_id)[:8]+"..", f"${o.subtotal:.2f}", f"${o.gst_amount:.2f}", f"${o.final_amount:.2f}", o.order_status, o.payment_status))
HTML += get_table("Orders", cols, rows)

# ── Cart Items ──
cols = ["ID (short)", "User ID", "Product ID", "Qty"]
rows = []
for ci in db.query(CartItem).all():
    rows.append((str(ci.id)[:8]+"..", str(ci.user_id)[:8]+"..", str(ci.product_id)[:8]+"..", ci.quantity))
HTML += get_table("Cart Items", cols, rows)

db.close()

HTML += "</body></html>"

path = os.path.join(tempfile.gettempdir(), "garment_db_view.html")
with open(path, "w", encoding="utf-8") as f:
    f.write(HTML)

webbrowser.open(f"file://{path}")
print(f"Opened {path}")
