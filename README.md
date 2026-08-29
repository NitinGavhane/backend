# dristi-backend

Python FastAPI backend for Dristi Fashions — combined API serving both the user mobile app (`dristi-user-app`) and the web storefront (`dristi-fashions-web`).

## Overview

This is the single backend for the entire Dristi Fashions platform. It handles:

- **Order management** — create, verify payment, finalize
- **Product & catalog** — CRUD for products, categories, brands
- **User accounts** — registration, profile, authentication (Google OAuth)
- **Payment processing** — Cashfree payments + Cash on Delivery
- **GST invoice generation** — tax-compliant invoices for every order
- **ShipRocket integration** — courier shipment fulfillment (optional)
- **Admin API** — dashboard endpoints for product/order/user management

## API Base URL

- Production: `https://api.dristi-backend.com/v1`
- Sandbox: `https://sandbox.dristi-backend.com/v1` (or local `http://localhost:8000`)

## Key Endpoints

| Category | Endpoints |
|----------|-----------|
| **Auth** | `POST /api/v1/auth/login`, `POST /api/v1/auth/google`, `GET /api/v1/auth/me` |
| **Orders** | `POST /api/v1/orders`, `GET /api/v1/orders`, `GET /api/v1/orders/{id}`, `POST /api/v1/orders/verify` |
| **Payments** | `POST /api/v1/payments/create`, `POST /api/v1/payments/verify`, `POST /api/v1/payments/refund` |
| **Products** | `GET /api/v1/products`, `GET /api/v1/products/{id}`, `POST /api/v1/products` (admin) |
| **Payments/Cashfree** | Config: `GET /api/v1/config/cashfree`, Create order: `POST /api/v1/payments/create`, Verify: `POST /api/v1/payments/verify` |
| **GST Invoices** | `GET /api/v1/invoices/{order_id}` |
| **ShipRocket** | `POST /api/v1/shiprocket/shipment`, status checks |

## Cashfree Integration

- `CASHFREE_CLIENT_ID` / `CASHFREE_CLIENT_SECRET` configured via `.env`
- `CASHFREE_ENV` = "sandbox" (test) or "production" (live)
- `CASHFREE_RETURN_URL` = where customer is redirected after paying
- Full flow: `create_payment` → Cashfree hosted checkout → `verify_payment` → order marked paid → GST invoice generated

## Configuration

Copy `.env.example` to `.env` and set:

```env
CASHFREE_CLIENT_ID="your_test_key_here"
CASHFREE_CLIENT_SECRET="your_test_secret_here"
CASHFREE_ENV="sandbox"
CASHFREE_RETURN_URL="http://localhost:3000/checkout/return"
SECRET_KEY="change-this-in-production"
DATABASE_URL="postgresql+pg8000://postgres:postgres@localhost:5432/garment_ecommerce"
```

## Running locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the development server
uvicorn app.main:app --reload          # http://localhost:8000
# or with Python directly
python -m app.main                   # http://localhost:8000
```

## Database

PostgreSQL is used via SQLAlchemy 2.0 style with `pg8000` driver. Migrations are managed with Alembic (if present).

## Related Repositories

- **User App**: `dristi-user-app` (Flutter mobile)
- **Web Storefront**: `dristi-fashions-web` (React + Vite)
- **Database**: PostgreSQL

## License

Proprietary — Dristi Fashions Platform