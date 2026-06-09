from app.core.database import SessionLocal
from sqlalchemy import text

try:
    db = SessionLocal()
    result = db.execute(text('SELECT 1 AS connected'))
    print(f'PostgreSQL Connected: {result.fetchone()[0]}')

    result = db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
    tables = [r[0] for r in result.fetchall()]
    print(f'Tables ({len(tables)}): {tables}')

    for table in ['categories', 'products', 'users', 'cart_items', 'orders', 'order_items', 'wallets', 'referrals', 'payments']:
        if table in tables:
            count = db.execute(text(f'SELECT COUNT(*) FROM {table}')).fetchone()[0]
            print(f'  {table}: {count} rows')
    db.close()
except Exception as e:
    print(f'ERROR: {e}')
