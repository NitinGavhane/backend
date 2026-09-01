"""Reset store to 'fresh' — remove all users/orders/revenue but keep products,
categories and store config (coupons, banners, payment methods, delivery
settings, referral settings). Admin accounts are preserved.

Usage:
  python scripts/reset_to_fresh.py --dry-run   # preview counts only
  python scripts/reset_to_fresh.py --confirm   # actually delete
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import SessionLocal

# Child tables first so FK constraints never break. `users` is last (only
# customers are deleted — admins are kept so the seller can still log in).
# Note referral_earnings has FKs to BOTH users and orders, so it must go
# before both.
DELETE_ORDER = [
    "referral_earnings",
    "gst_invoices",
    "order_items",
    "payments",
    "orders",
    "cart_items",
    "wallet_transactions",
    "referral_share_clicks",
    "addresses",
    "reviews",
    "wishlist_items",
    "contact_messages",
    "newsletter_subscribers",
    "blog_posts",
]

KEEP_TABLES = [
    "products",
    "product_variants",
    "product_images",
    "categories",
    "coupons",
    "banners",
    "payment_methods",
    "delivery_settings",
    "referral_settings",
]

DRY_RUN = "--dry-run" in sys.argv
CONFIRM = "--confirm" in sys.argv

db = SessionLocal()

print("=== BEFORE ===")
for t in DELETE_ORDER + ["users"]:
    n = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
    print(f"  {t}: {n}")

admins = db.execute(text("SELECT id, email, full_name, wallet_balance FROM users WHERE role='admin'")).fetchall()
customers = db.execute(text("SELECT COUNT(*) FROM users WHERE role='customer'")).scalar()
print(f"  admins kept: {len(admins)}")
for a in admins:
    print(f"    - {a[1]} ({a[2]}) wallet=${a[3]:.2f}")

print("\n=== USER-GENERATED CONTENT (cleared) ===")
for t in DELETE_ORDER:
    n = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
    if n:
        print(f"  {t}: {n}")

if not DRY_RUN and not CONFIRM:
    print("\nThis will PERMANENTLY delete the rows above. Re-run with --confirm to execute, or --dry-run for a read-only preview.")
    db.close()
    sys.exit(1)

if DRY_RUN:
    print("\nDry run — nothing was deleted.")
    db.close()
    sys.exit(0)

if len(admins) == 0:
    print("\nREFUSING: no admin users found. Aborting to avoid locking you out of the admin app.")
    db.close()
    sys.exit(1)

print("\n=== DELETING ===")
try:
    for t in DELETE_ORDER:
        n = db.execute(text(f"DELETE FROM {t} RETURNING id")).rowcount
        print(f"  deleted from {t}: {n}")

    n_customers = db.execute(text("DELETE FROM users WHERE role='customer' RETURNING id")).rowcount
    print(f"  deleted customer users: {n_customers}")

    # Zero wallet balances on retained admins so revenue/wallet reads 0.
    n_zeroed = db.execute(text("UPDATE users SET wallet_balance = 0.0")).rowcount
    print(f"  zeroed wallet_balance on retained users: {n_zeroed}")

    db.commit()
    print("\n=== AFTER ===")
    for t in KEEP_TABLES:
        n = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        print(f"  KEPT {t}: {n}")
    for t in DELETE_ORDER + ["users"]:
        n = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        print(f"  {t}: {n}")
    print("\nDone. Store is fresh: products + categories + store config only.")
except Exception as e:
    db.rollback()
    print(f"\nERROR, transaction rolled back: {e}")
    sys.exit(1)
finally:
    db.close()