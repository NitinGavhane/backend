from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.database import Base, engine
from app.api import (
    auth, products, categories, cart, orders,
    addresses, users, wishlist, wallet, reviews, notifications,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(addresses.router)
app.include_router(users.router)
app.include_router(wishlist.router)
app.include_router(wallet.router)
app.include_router(reviews.router)
app.include_router(notifications.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": settings.app_name}


@app.get("/api/banners")
def get_banners():
    return {
        "banners": [
            {
                "title": "Summer Collection",
                "subtitle": "Up to 50% Off",
                "tag": "Trending Now",
            },
            {
                "title": "New Arrivals",
                "subtitle": "Spring 2026 Styles",
                "tag": "Fresh Drops",
            },
            {
                "title": "Festival Edit",
                "subtitle": "Ethnic Wear Sale",
                "tag": "Limited Time",
            },
        ]
    }


@app.get("/api/payment-methods")
def get_payment_methods():
    return {
        "paymentMethods": [
            {"name": "Google Pay", "isPopular": True},
            {"name": "PhonePe", "isPopular": True},
            {"name": "Paytm", "isPopular": True},
            {"name": "Credit Card", "isPopular": False},
            {"name": "Debit Card", "isPopular": False},
            {"name": "Net Banking", "isPopular": False},
            {"name": "Cash on Delivery", "isPopular": False},
        ]
    }
