import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Garment E-commerce Platform API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str | None = None

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "garment_ecommerce"

    @property
    def db_url(self) -> str:
        if self.DATABASE_URL:
            raw = self.DATABASE_URL
            if raw.startswith("postgresql://"):
                raw = raw.replace("postgresql://", "postgresql+pg8000://", 1)
            return raw
        return f"postgresql+pg8000://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # TLS to the database: "auto" turns it on for any host reachable over the
    # internet and off for a loopback/private-network host (see database.py);
    # "require" / "disable" override that.
    DB_SSL: str = "auto"

    SECRET_KEY: str = "your-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    CORS_ORIGINS: str = "*"

    # Public storefront origin. Shared product/referral links are built from
    # this, so a link a customer sends is a real, clickable URL. Keep it in step
    # with AppLinks.siteUrl in the user app.
    SITE_URL: str = "https://dristifashions.com"

    # Email delivery via AWS SES. Two transports are supported:
    #   "ses"  -> the SES SendEmail API through boto3. Preferred in production:
    #             picks up credentials from the EC2 instance role (same as S3)
    #             and needs no long-lived SMTP secret.
    #   "smtp" -> sendmail over the SES SMTP relay (email-smtp.<region>.amazonaws.com).
    # If the configured backend fails at runtime, email_service falls back to the
    # other one automatically so a delivery path is never silently down.
    EMAIL_BACKEND: str = "ses"
    SMTP_HOST: str = "email-smtp.ap-south-1.amazonaws.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    # The verified sender every user-facing email is sent From. Must be a
    # verified identity (or inside the verified domain dristifashions.com) or
    # SES will reject the send — also true in sandbox mode.
    SMTP_FROM_EMAIL: str = "info@dristifashions.com"
    # SES API transport settings. Client uses instance-role / env credentials
    # unless explicit ones are supplied here. SES_CONFIGURATION_SET is optional
    # (enables bounce/complaint tracking and open/click when created in SES).
    SES_REGION: str = "ap-south-1"
    SES_ACCESS_KEY_ID: str = ""
    SES_SECRET_ACCESS_KEY: str = ""
    SES_CONFIGURATION_SET: str = ""

    # WhatsApp notifications — provider-agnostic seam. Leave WHATSAPP_PROVIDER
    # empty to keep WhatsApp as a logged no-op (email still delivers everything);
    # set it to "twilio" and supply the credentials to switch it on.
    WHATSAPP_PROVIDER: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = ""  # Twilio WhatsApp sender number, e.g. +14155238886
    # Approved Content-API template SIDs, keyed by our internal template name
    # (order_placed, order_dispatched, order_delivered, return_approved,
    # return_rejected, return_picked_up). JSON mapping; empty dict until set.
    TWILIO_TEMPLATES: dict = {}

    # Google OAuth — client ID for verifying ID tokens server-side.
    GOOGLE_CLIENT_ID: str = ""

    # Cashfree Payments — the payment gateway for every online method. Keys
    # are supplied via env. "sandbox" routes to the test API (no real money);
    # "production" is the live gateway. Test keys start with TEST/cfsk_ma_test_.
    CASHFREE_CLIENT_ID: str = ""
    CASHFREE_CLIENT_SECRET: str = ""
    CASHFREE_ENV: str = "sandbox"
    # Where the customer returns after paying on Cashfree's hosted page.
    # `{order_id}` is Cashfree's substitution token (use the literal braces).
    CASHFREE_RETURN_URL: str = ""

    @property
    def cashfree_base_url(self) -> str:
        if self.CASHFREE_ENV.lower() == "production":
            return "https://api.cashfree.com/pg"
        return "https://sandbox.cashfree.com/pg"

    # Seller identity printed on GST tax invoices. Overridable via env; the
    # defaults mirror the registered business details shown on the invoice
    # sample. The seller state drives the intra/inter-state GST label already
    # computed at checkout (West Bengal).
    SELLER_NAME: str = "Dristi Dhimahi Vyapaar Pvt Ltd"
    SELLER_COMPANY_ID: str = "U46109WB2023PTC265442"
    SELLER_GSTIN: str = "19AAKCD3509Q1Z1"
    SELLER_ADDRESS: str = "212 GIRISH GHOSH ROAD\nROOM NO -430 RANGOLI MALL\nHOWRAH West Bengal 711202\nIndia"
    SELLER_PHONE: str = "7003871460"
    SELLER_STATE: str = "West Bengal"
    SELLER_EMAIL: str = "dristidhimahivyapaar@gmail.com"

    # Default HSN/SAC printed on invoices. Products do not carry their own HSN,
    # so every line item uses this garment HSN unless a per-product code is
    # added later.
    DEFAULT_HSN: str = "611300"

    # Logo embedded in the invoice header. Resolved relative to the backend
    # root (the file lives at backend/app/static/logo.png by default).
    INVOICE_LOGO_PATH: str = "app/static/logo.png"

    # Authorized-signature image stamped on the invoice. Resolved relative to
    # the backend root (the file lives at backend/app/static/signature.png by
    # default). A copy also ships in the user/admin app and website assets so
    # any of them can reference it for display.
    INVOICE_SIGNATURE_PATH: str = "app/static/signature.png"

    # S3 image uploads (banners). Credentials come from the EC2 instance role,
    # so only the bucket/region are configured here. S3_PUBLIC_BASE_URL lets a
    # CDN front the bucket; when empty the direct S3 object URL is used.
    AWS_REGION: str = "ap-south-1"
    S3_UPLOAD_BUCKET: str = ""
    S3_PUBLIC_BASE_URL: str = ""

    # ShipRocket (courier shipment fulfilment). When disabled, outbound orders
    # still go through the in-house dispatch/OTP flow; when enabled, dispatching
    # an order creates a real ShipRocket shipment and stores courier tracking.
    SHIPROCKET_ENABLED: bool = False
    SHIPROCKET_API_BASE: str = "https://apiv2.shiprocket.in/v1/external"
    # ShipRocket API user credentials (Settings -> API -> Create API User).
    # The token is the API user's password/API key used to obtain a JWT from
    # the /auth/login endpoint; the email is the API user's email address.
    # The resulting JWT is cached and used as the Bearer token for all calls.
    SHIPROCKET_EMAIL: str = ""
    SHIPROCKET_TOKEN: str = ""
    # Pickup location name exactly as named in the ShipRocket account (Settings
    # -> Pickup Locations). Requests fail with 422 if this does not match.
    SHIPROCKET_PICKUP_LOCATION: str = ""
    # Defaults used when sending an order (weight in kg, dims in cm). Products
    # do not carry dimensions, so a single store default keeps the payload valid.
    SHIPROCKET_DEFAULT_WEIGHT: float = 0.5
    SHIPROCKET_DEFAULT_LENGTH: float = 20.0
    SHIPROCKET_DEFAULT_BREADTH: float = 15.0
    SHIPROCKET_DEFAULT_HEIGHT: float = 10.0

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
