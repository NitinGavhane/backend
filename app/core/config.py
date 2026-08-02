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

    # Amazon SES SMTP (email-smtp.<region>.amazonaws.com, 587 STARTTLS). The
    # username is the SES SMTP user's IAM access key id; the password is the
    # SigV4-derived SES SMTP password (not the IAM secret itself). From is the
    # verified business address info@dristifashions.com.
    SMTP_HOST: str = "email-smtp.ap-south-1.amazonaws.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "info@dristifashions.com"

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

    # Razorpay — the only supported payment gateway. Keys are supplied via env
    # (test keys start with rzp_test_, live keys with rzp_live_).
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # Seller identity printed on GST tax invoices. Overridable via env once the
    # real GSTIN/registered address is available; the defaults keep invoices
    # rendering sensibly in the meantime. The seller state drives the
    # intra/inter-state GST label already computed at checkout (West Bengal).
    SELLER_NAME: str = "Dristi Fashions"
    SELLER_GSTIN: str = "19AAAAA0000A1Z5"
    SELLER_ADDRESS: str = "West Bengal, India"
    SELLER_STATE: str = "West Bengal"
    SELLER_EMAIL: str = "support@dristifashions.com"

    # S3 image uploads (banners). Credentials come from the EC2 instance role,
    # so only the bucket/region are configured here. S3_PUBLIC_BASE_URL lets a
    # CDN front the bucket; when empty the direct S3 object URL is used.
    AWS_REGION: str = "ap-south-1"
    S3_UPLOAD_BUCKET: str = ""
    S3_PUBLIC_BASE_URL: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
