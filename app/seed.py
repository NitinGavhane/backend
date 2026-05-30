"""Seed script to populate the database with mock data matching the Flutter frontend."""

import uuid
from datetime import datetime, timezone, timedelta
from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.product import Product
from app.models.address import Address
from app.models.order import (
    Order, OrderItem, OrderStatus,
    ReturnReplaceRequest, ReturnReplaceRequestItem,
    ReturnReplaceType, ReturnReplaceStatus,
)
from app.models.cart import CartItem
from app.models.review import Review
from app.models.notification import Notification
from app.models.wallet import WalletTransaction


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(User).count() > 0:
        print("Database already seeded. Skipping.")
        db.close()
        return

    # ── Users ──
    user = User(
        id="u1",
        full_name="Priya Sharma",
        email="priya.sharma@email.com",
        phone="+91 98765 43210",
        hashed_password=hash_password("user123"),
        wallet_balance=250.00,
        referral_code="PRIYA250",
        is_verified=True,
        role=UserRole.user,
    )
    db.add(user)

    user2 = User(
        id="u2",
        full_name="Test User",
        email="user@test.com",
        phone="+91 98765 43211",
        hashed_password=hash_password("user123"),
        wallet_balance=100.00,
        referral_code="TEST100",
        is_verified=True,
        role=UserRole.user,
    )
    db.add(user2)

    # ── Categories ──
    categories_data = [
        ("cat1", "Men", "man", "#2D3436", 24),
        ("cat2", "Women", "woman", "#E84393", 32),
        ("cat3", "Kids", "child_care", "#00B894", 18),
        ("cat4", "Accessories", "watch", "#6C5CE7", 15),
        ("cat5", "Footwear", "directions_run", "#8B5CF6", 20),
        ("cat6", "Ethnic", "diamond", "#EC4899", 14),
        ("cat7", "Western", "checkroom", "#14B8A6", 22),
        ("cat8", "Sports", "fitness_center", "#F97316", 16),
    ]

    for cat_id, name, icon, color, count in categories_data:
        db.add(Category(id=cat_id, name=name, icon=icon, color=color, product_count=count))

    # ── Products ──
    products_data = [
        ("p1", "Premium Cotton T-Shirt", "High-quality 100% organic cotton t-shirt with a relaxed fit.", "Urban Threads", "Men", "cat1", 29.99, 49.99, 4.5, 128, 40, ["S", "M", "L", "XL", "XXL"], ["Black", "White", "Navy", "Gray"], True, False, "Best Seller", 150),
        ("p2", "Slim Fit Blazer", "Modern slim fit blazer crafted from premium wool blend.", "Sartorial Edge", "Men", "cat1", 149.99, 249.99, 4.7, 89, 40, ["M", "L", "XL"], ["Charcoal", "Navy", "Black"], True, True, "New", 45),
        ("p3", "Floral Summer Dress", "Beautiful floral print dress with a flattering A-line silhouette.", "Bloom & Co", "Women", "cat2", 59.99, 89.99, 4.6, 215, 33, ["XS", "S", "M", "L", "XL"], ["Blue Floral", "Pink Floral", "Yellow Floral"], True, False, "Popular", 80),
        ("p4", "Designer Handbag", "Luxury handbag crafted from genuine leather with gold-toned hardware.", "Luxe Carry", "Accessories", "cat4", 199.99, 349.99, 4.8, 156, 43, ["One Size"], ["Tan", "Black", "Burgundy"], True, False, "Hot Deal", 25),
        ("p5", "Denim Jacket", "Classic denim jacket with a modern twist.", "Rebel Denim", "Men", "cat1", 79.99, 119.99, 4.4, 94, 33, ["S", "M", "L", "XL"], ["Light Wash", "Dark Wash", "Black"], False, True, "New", 60),
        ("p6", "Yoga Leggings", "High-waist compression leggings with moisture-wicking technology.", "Flex Fit", "Women", "cat2", 44.99, 69.99, 4.7, 312, 36, ["XS", "S", "M", "L", "XL"], ["Black", "Navy", "Burgundy", "Teal"], True, False, "Best Seller", 200),
        ("p7", "Kids Animal T-Shirt", "Fun animal print t-shirt for kids. Made from soft cotton.", "Tiny Tots", "Kids", "cat3", 14.99, 24.99, 4.3, 67, 40, ["2-3Y", "3-4Y", "5-6Y", "7-8Y"], ["Blue", "Pink", "Green"], False, False, "Sale", 120),
        ("p8", "Leather Sneakers", "Premium leather sneakers with cushioned sole for all-day comfort.", "Sole Society", "Footwear", "cat5", 89.99, 149.99, 4.6, 178, 40, ["7", "8", "9", "10", "11", "12"], ["White", "Black", "Tan"], True, False, "Trending", 90),
        ("p9", "Silk Evening Gown", "Elegant floor-length evening gown in pure silk.", "Velvet Rose", "Women", "cat2", 299.99, 499.99, 4.9, 42, 40, ["XS", "S", "M", "L"], ["Midnight Blue", "Burgundy", "Emerald"], True, True, "Premium", 15),
        ("p10", "Cashmere Sweater", "Luxuriously soft cashmere sweater with ribbed cuffs.", "Nordic Knit", "Men", "cat1", 129.99, 189.99, 4.5, 73, 32, ["S", "M", "L", "XL", "XXL"], ["Gray", "Navy", "Burgundy", "Forest Green"], False, False, "Warm Pick", 35),
        ("p11", "Kids Raincoat Set", "Waterproof raincoat with matching boots.", "Rainbow Kids", "Kids", "cat3", 39.99, 59.99, 4.4, 55, 33, ["2-3Y", "3-4Y", "5-6Y"], ["Yellow", "Red", "Blue"], False, True, "New", 40),
        ("p12", "Gold Hoop Earrings", "Stunning 18K gold-plated hoop earrings with a polished finish.", "Gleam & Glow", "Accessories", "cat4", 49.99, 89.99, 4.7, 203, 44, ["Small", "Medium", "Large"], ["Gold", "Silver", "Rose Gold"], True, False, "Best Seller", 150),
        ("p13", "Running Shoes", "Lightweight running shoes with responsive cushioning.", "Stride X", "Footwear", "cat5", 119.99, 179.99, 4.6, 245, 33, ["7", "8", "9", "10", "11", "12", "13"], ["Black/White", "Blue/Neon", "Red/Black"], True, False, "Performance", 75),
        ("p14", "Embroidered Kurta Set", "Traditional embroidered kurta set with churidar and dupatta.", "Ethnic Elegance", "Women", "cat2", 89.99, 149.99, 4.8, 167, 40, ["S", "M", "L", "XL", "XXL"], ["Pink", "Green", "Blue", "Yellow"], True, False, "Festival Special", 55),
        ("p15", "Woolen Scarf", "Handwoven woolen scarf with traditional patterns.", "Cozy Crafts", "Accessories", "cat4", 34.99, 54.99, 4.3, 88, 36, ["One Size"], ["Red", "Gray", "Navy", "Mustard"], False, False, "Winter Wear", 100),
        ("p16", "Cargo Joggers", "Comfortable cargo joggers with multiple pockets.", "Street Vibe", "Men", "cat1", 49.99, 79.99, 4.4, 134, 38, ["S", "M", "L", "XL", "XXL"], ["Black", "Olive", "Gray", "Navy"], False, True, "Trending", 110),
    ]

    for p in products_data:
        db.add(Product(
            id=p[0], title=p[1], description=p[2], brand=p[3],
            category=p[4], category_id=p[5], price=p[6], original_price=p[7],
            rating=p[8], review_count=p[9], discount_percentage=p[10],
            sizes=p[11], colors=p[12], is_featured=p[13], is_new=p[14],
            badge=p[15], stock=p[16],
        ))

    # ── Addresses ──
    addr1 = Address(
        id="addr1", user_id="u1",
        full_name="Priya Sharma", phone="+91 98765 43210",
        street="42, MG Road, Indiranagar", city="Bengaluru",
        state="Karnataka", pincode="560038",
        is_default=True, type="Home",
    )
    addr2 = Address(
        id="addr2", user_id="u1",
        full_name="Priya Sharma", phone="+91 98765 43210",
        street="Suite 501, Tech Park, Whitefield", city="Bengaluru",
        state="Karnataka", pincode="560066",
        is_default=False, type="Work",
    )
    db.add_all([addr1, addr2])

    # ── Orders ──
    now = datetime.now(timezone.utc)

    order1 = Order(
        id="ord1", user_id="u1", order_number="ORD-2026-001",
        subtotal=104.97, shipping=0, discount=15.75, gst=13.41, total=102.63,
        status=OrderStatus.out_for_delivery, address_id="addr1",
        payment_method="UPI (Google Pay)",
        created_at=now - timedelta(days=6),
        estimated_delivery=now - timedelta(days=2),
        tracking_id="TRK12847003",
    )
    db.add(order1)

    oi1 = OrderItem(id="oi1", order_id="ord1", product_id="p1", quantity=2, price=29.99, size="M", color="Black")
    oi2 = OrderItem(id="oi2", order_id="ord1", product_id="p6", quantity=1, price=44.99, size="S", color="Navy")
    db.add_all([oi1, oi2])

    order2 = Order(
        id="ord2", user_id="u1", order_number="ORD-2026-002",
        subtotal=199.99, shipping=0, discount=0, gst=25.99, total=225.98,
        status=OrderStatus.processing, address_id="addr2",
        payment_method="Credit Card",
        created_at=now - timedelta(days=5),
        estimated_delivery=now,
    )
    db.add(order2)

    oi3 = OrderItem(id="oi3", order_id="ord2", product_id="p4", quantity=1, price=199.99, size="One Size", color="Tan")
    db.add(oi3)

    order3 = Order(
        id="ord3", user_id="u1", order_number="ORD-2026-003",
        subtotal=349.98, shipping=0, discount=50.00, gst=38.99, total=338.97,
        status=OrderStatus.delivered, address_id="addr1",
        payment_method="Cash on Delivery",
        created_at=now - timedelta(days=10),
        estimated_delivery=now - timedelta(days=5),
    )
    db.add(order3)

    oi4 = OrderItem(id="oi4", order_id="ord3", product_id="p9", quantity=1, price=299.99, size="M", color="Midnight Blue")
    oi5 = OrderItem(id="oi5", order_id="ord3", product_id="p12", quantity=1, price=49.99, size="Medium", color="Gold")
    db.add_all([oi4, oi5])

    rr1 = ReturnReplaceRequest(
        id="rr1", order_id="ord3",
        type=ReturnReplaceType.return_request,
        status=ReturnReplaceStatus.submitted,
        reason="Item arrived damaged",
        created_at=now - timedelta(days=4),
    )
    db.add(rr1)
    db.add(ReturnReplaceRequestItem(id=str(uuid.uuid4()), request_id="rr1", order_item_id="oi4", quantity=1))

    order4 = Order(
        id="ord4", user_id="u1", order_number="ORD-2026-004",
        subtotal=179.98, shipping=10.00, discount=25.00, gst=21.45, total=186.43,
        status=OrderStatus.placed, address_id="addr1",
        payment_method="UPI (PhonePe)",
        created_at=now - timedelta(days=4),
        estimated_delivery=now + timedelta(days=1),
        tracking_id="TRK12847089",
    )
    db.add(order4)
    oi6 = OrderItem(id="oi6", order_id="ord4", product_id="p14", quantity=2, price=89.99, size="M", color="Pink")
    db.add(oi6)

    # ── Cart Items ──
    db.add(CartItem(id="ci1", user_id="u1", product_id="p1", quantity=2, selected_size="M", selected_color="Black"))
    db.add(CartItem(id="ci2", user_id="u1", product_id="p6", quantity=1, selected_size="S", selected_color="Black"))
    db.add(CartItem(id="ci3", user_id="u1", product_id="p12", quantity=1, selected_size="Small", selected_color="Gold"))

    # ── Reviews ──
    reviews_data = [
        ("r1", "u1", "p1", 5, "Great quality! The fabric is super soft and comfortable."),
        ("r2", "u1", "p6", 4, "Very comfortable for yoga. true to size."),
        ("r3", "u1", "p12", 5, "Beautiful earrings! Look very elegant."),
        ("r4", "u1", "p8", 4, "Stylish and comfortable sneakers."),
    ]
    for rid, uid, pid, rating, comment in reviews_data:
        db.add(Review(id=rid, user_id=uid, product_id=pid, rating=rating, comment=comment, created_at=now - timedelta(days=30)))

    # ── Notifications ──
    notifications_data = [
        ("n1", "u1", "Order Delivered", "Your order ORD-2026-003 has been delivered.", "success"),
        ("n2", "u1", "Return Request Update", "Your return request for Silk Evening Gown has been approved.", "info"),
        ("n3", "u1", "Flash Sale Alert", "Extra 20% off on ethnic wear! Limited period offer.", "promo"),
        ("n4", "u1", "Price Drop", "Premium Cotton T-Shirt is now at ₹1,999", "alert"),
        ("n5", "u1", "Order Shipped", "Your order ORD-2026-001 is out for delivery.", "order"),
        ("n6", "u1", "Welcome!", "Welcome to Garment! Enjoy your shopping experience.", "info"),
    ]
    for nid, uid, title, message, ntype in notifications_data:
        db.add(Notification(id=nid, user_id=uid, title=title, message=message, type=ntype, is_read=False, created_at=now - timedelta(days=1)))

    # ── Wallet Transactions ──
    txns_data = [
        ("t1", "u1", 500.00, "credit", "Money added to wallet"),
        ("t2", "u1", -150.00, "debit", "Order payment ORD-2026-001"),
        ("t3", "u1", 100.00, "credit", "Referral bonus from user"),
        ("t4", "u1", -200.00, "debit", "Order payment ORD-2026-002"),
    ]
    for tid, uid, amount, ttype, desc in txns_data:
        db.add(WalletTransaction(id=tid, user_id=uid, amount=amount, type=ttype, description=desc, created_at=now - timedelta(days=2)))

    # ── Wishlist ──
    from app.models.wishlist import wishlist_table
    for pid in ["p1", "p3", "p8", "p12"]:
        db.execute(wishlist_table.insert().values(user_id="u1", product_id=pid))

    db.commit()
    db.close()
    print("Database seeded successfully with mock data!")


if __name__ == "__main__":
    seed()
