import httpx
import random
import string
import sys
import time

BASE_URL = "http://127.0.0.1:8000"
suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
TIMEOUT = 30

def banner(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")

def req(method, path, **kwargs):
    url = f"{BASE_URL}{path}"
    kwargs.setdefault("timeout", TIMEOUT)
    r = getattr(httpx, method)(url, **kwargs)
    status = r.status_code
    ok = "OK" if status < 400 else "FAIL"
    print(f"  {method.upper():6} {path}  ->  {status} {ok}")
    if status >= 400:
        try:
            print(f"       Body: {r.json()}")
        except Exception:
            print(f"       Body: {r.text[:200]}")
    return r

def main():
    print(f"Testing APIs at {BASE_URL}")
    print(f"Test suffix: {suffix}")
    email = f"testuser_{suffix}@example.com"
    admin_email = "admin@garment.com"
    admin_pass = "Admin@1234"
    password = "Test@1234"
    name = f"Test User {suffix}"

    customer_token = None
    admin_token = None
    refresh_token_val = None
    created_category_id = None
    created_product_id = None
    created_order_id = None
    created_cart_item_id = None

    # ── Auth Endpoints ──
    banner("1. AUTH ENDPOINTS")

    # 1a. Register
    r = req("post", "/api/v1/auth/register", json={
        "full_name": name,
        "email": email,
        "phone": f"99999{suffix[:5]}",
        "password": password,
    })
    if r.status_code == 200:
        print(f"       User registered: {email}")

    # 1b. Verify OTP (uses hardcoded "000000")
    r = req("post", "/api/v1/auth/verify-otp", json={
        "email": email,
        "otp": "000000",
    })

    # 1c. Login (customer)
    r = req("post", "/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    if r.status_code == 200:
        data = r.json()
        customer_token = data["access_token"]
        refresh_token_val = data["refresh_token"]
        print(f"       Customer login OK")

    # 1d. Get profile (JWT required)
    if customer_token:
        r = req("get", "/api/v1/auth/me", headers={"Authorization": f"Bearer {customer_token}"})
        if r.status_code == 200:
            print(f"       Profile: {r.json()['email']}")

    # 1e. Refresh token
    if refresh_token_val:
        r = req("post", "/api/v1/auth/refresh-token", json={"refresh_token": refresh_token_val})
        if r.status_code == 200:
            customer_token = r.json()["access_token"]
            print(f"       Token refreshed OK")

    # ── Public Endpoints ──
    banner("2. PUBLIC ENDPOINTS (products / categories)")

    # 2a. List categories (public)
    r = req("get", "/api/v1/categories")
    categories = r.json() if r.status_code == 200 else []

    # 2b. List products (public)
    r = req("get", "/api/v1/products")
    products = r.json() if r.status_code == 200 else []

    # ── Admin Endpoints (login first) ──
    banner("3. ADMIN AUTH")

    # 3a. Admin login
    r = req("post", "/api/v1/admin/login", json={
        "email": admin_email,
        "password": admin_pass,
    })
    if r.status_code == 200:
        admin_token = r.json()["access_token"]
        print(f"       Admin login OK")
    else:
        print("  ERROR: Could not login as admin. Is the server running with fresh DB?")
        sys.exit(1)

    # 3b. Dashboard
    r = req("get", "/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {admin_token}"})
    if r.status_code == 200:
        print(f"       Dashboard: {r.json()}")

    # 3c. List users (admin)
    r = req("get", "/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    if r.status_code == 200:
        print(f"       Users count: {len(r.json())}")

    # 3d. List orders (admin)
    r = req("get", "/api/v1/admin/orders", headers={"Authorization": f"Bearer {admin_token}"})
    if r.status_code == 200:
        print(f"       Orders count: {len(r.json())}")

    # 3e. List referrals (admin)
    r = req("get", "/api/v1/admin/referrals", headers={"Authorization": f"Bearer {admin_token}"})
    if r.status_code == 200:
        print(f"       Referrals count: {len(r.json())}")

    # ── Category CRUD (admin) ──
    banner("4. CATEGORY CRUD (admin)")

    cat_slug = f"test-cat-{suffix}"
    r = req("post", "/api/v1/admin/categories", headers={"Authorization": f"Bearer {admin_token}"}, json={
        "name": f"Test Category {suffix}",
        "slug": cat_slug,
        "description": "Created by test script",
    })
    if r.status_code == 200:
        created_category_id = r.json()["id"]
        print(f"       Created category: {created_category_id}")

    if created_category_id:
        r = req("put", f"/api/v1/admin/categories/{created_category_id}",
                headers={"Authorization": f"Bearer {admin_token}"}, json={
            "name": f"Updated Category {suffix}",
            "description": "Updated description",
        })
        if r.status_code == 200:
            print(f"       Updated category OK")

        r = req("delete", f"/api/v1/admin/categories/{created_category_id}",
                headers={"Authorization": f"Bearer {admin_token}"})
        if r.status_code == 200:
            print(f"       Deleted category OK")

        # Re-create it for product tests
        r = req("post", "/api/v1/admin/categories", headers={"Authorization": f"Bearer {admin_token}"}, json={
            "name": f"Test Category {suffix}",
            "slug": f"{cat_slug}-recreated",
            "description": "Recreated for product tests",
        })
        if r.status_code == 200:
            created_category_id = r.json()["id"]
            print(f"       Recreated category: {created_category_id}")

    # ── Product CRUD (admin) ──
    banner("5. PRODUCT CRUD (admin)")

    if created_category_id:
        sku = f"SKU-{suffix}"
        r = req("post", "/api/v1/admin/products", headers={"Authorization": f"Bearer {admin_token}"}, json={
            "category_id": created_category_id,
            "title": f"Test Product {suffix}",
            "description": "Test product description",
            "brand": "TestBrand",
            "sku": sku,
            "price": 999.0,
            "discount_price": 799.0,
            "gst_percentage": 18.0,
            "stock": 100,
            "featured": True,
            "variants": [
                {"size": "M", "color": "Red", "stock": 50, "price": 799.0},
                {"size": "L", "color": "Blue", "stock": 30, "price": 799.0},
            ],
            "images": [
                {"image_url": "https://example.com/img1.jpg", "is_primary": True},
            ],
        })
        if r.status_code == 200:
            created_product_id = r.json()["id"]
            print(f"       Created product: {created_product_id}")
        else:
            print(f"       Create failed: {r.text}")

    if created_product_id:
        r = req("put", f"/api/v1/admin/products/{created_product_id}",
                headers={"Authorization": f"Bearer {admin_token}"}, json={
            "price": 899.0,
            "stock": 80,
        })
        if r.status_code == 200:
            print(f"       Updated product OK")

        r = req("delete", f"/api/v1/admin/products/{created_product_id}",
                headers={"Authorization": f"Bearer {admin_token}"})
        if r.status_code == 200:
            print(f"       Deleted product OK")

        # Re-create for order tests (with same SKU+1 to avoid unique constraint)
        sku2 = f"SKU-{suffix}-2"
        r = req("post", "/api/v1/admin/products", headers={"Authorization": f"Bearer {admin_token}"}, json={
            "category_id": created_category_id,
            "title": f"Test Product {suffix}",
            "description": "Test product for ordering",
            "brand": "TestBrand",
            "sku": sku2,
            "price": 500.0,
            "gst_percentage": 18.0,
            "stock": 50,
            "featured": False,
            "variants": [],
            "images": [],
        })
        if r.status_code == 200:
            created_product_id = r.json()["id"]
            print(f"       Recreated product: {created_product_id}")

    # ── Cart Endpoints (JWT required) ──
    banner("6. CART ENDPOINTS (customer JWT)")

    if customer_token and created_product_id:
        r = req("post", "/api/v1/cart/add", headers={"Authorization": f"Bearer {customer_token}"}, json={
            "product_id": created_product_id,
            "quantity": 2,
        })
        if r.status_code == 200:
            print(f"       Added to cart OK")

        r = req("get", "/api/v1/cart", headers={"Authorization": f"Bearer {customer_token}"})
        cart_item_id = None
        if r.status_code == 200:
            cart = r.json()
            items = cart.get("items", [])
            print(f"       Cart items: {len(items)}")
            if items:
                cart_item_id = items[0]["id"]

        if cart_item_id:
            r = req("put", "/api/v1/cart/update", headers={"Authorization": f"Bearer {customer_token}"}, json={
                "cart_item_id": cart_item_id,
                "quantity": 3,
            })
            if r.status_code == 200:
                print(f"       Updated cart OK")

    # ── Order Endpoints (JWT required) ──
    banner("7. ORDER ENDPOINTS (customer JWT)")

    if customer_token and created_product_id:
        r = req("post", "/api/v1/orders", headers={"Authorization": f"Bearer {customer_token}"}, json={
            "shipping_address": "123 Test Street, Test City, 123456",
            "items": [
                {"product_id": created_product_id, "quantity": 1}
            ],
        })
        if r.status_code == 200:
            created_order_id = r.json()["id"]
            print(f"       Created order: {created_order_id}")
        else:
            print(f"       Order create failed: {r.text[:300]}")

        r = req("get", "/api/v1/orders", headers={"Authorization": f"Bearer {customer_token}"})
        if r.status_code == 200:
            print(f"       User orders count: {len(r.json())}")

        if created_order_id:
            r = req("get", f"/api/v1/orders/{created_order_id}",
                    headers={"Authorization": f"Bearer {customer_token}"})
            if r.status_code == 200:
                print(f"       Order detail OK")

            # Admin: update order status
            r = req("put", f"/api/v1/orders/{created_order_id}/status",
                    headers={"Authorization": f"Bearer {admin_token}"}, json={
                "status": "processing",
            })
            if r.status_code == 200:
                print(f"       Admin updated order status OK")

    # ── Referral Endpoints (JWT required) ──
    banner("8. REFERRAL ENDPOINTS (customer JWT)")

    if customer_token:
        r = req("get", "/api/v1/referral/me", headers={"Authorization": f"Bearer {customer_token}"})
        if r.status_code == 200:
            print(f"       Referral stats: {r.json()}")

        r = req("get", "/api/v1/referral/history", headers={"Authorization": f"Bearer {customer_token}"})
        if r.status_code == 200:
            print(f"       Referral history: {len(r.json())} entries")

    # ── Wallet Endpoints (JWT required) ──
    banner("9. WALLET ENDPOINTS (customer JWT)")

    if customer_token:
        r = req("get", "/api/v1/wallet/balance", headers={"Authorization": f"Bearer {customer_token}"})
        if r.status_code == 200:
            print(f"       Wallet balance: {r.json()}")

        r = req("get", "/api/v1/wallet/transactions", headers={"Authorization": f"Bearer {customer_token}"})
        if r.status_code == 200:
            print(f"       Wallet transactions: {len(r.json())} entries")

    # ── Summary ──
    banner("TEST COMPLETE")
    print(f"  Customer email: {email}")
    print(f"  Password:       {password}")
    print(f"  Admin email:    {admin_email}")
    print(f"  Admin password: {admin_pass}")
    print(f"\n  OpenAPI docs: {BASE_URL}/docs")
    print(f"  ReDoc:        {BASE_URL}/redoc")


if __name__ == "__main__":
    main()
