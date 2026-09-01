import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
def q(s):
    return db.execute(text(s)).scalar()

print('total_users (non-admin):', q("SELECT COUNT(*) FROM users WHERE role <> 'admin'"))
print('total_products:', q('SELECT COUNT(*) FROM products'))
print('total_orders:', q('SELECT COUNT(*) FROM orders'))
print('total_revenue:', q("SELECT COALESCE(SUM(final_amount),0) FROM orders WHERE payment_status='paid'"))
print('pending_orders:', q("SELECT COUNT(*) FROM orders WHERE order_status='placed'"))
db.close()