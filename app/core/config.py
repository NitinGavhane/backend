from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Garment E-commerce API"
    debug: bool = False

    database_url: str = "postgresql://user:password@localhost:5432/garment_ecommerce"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    redis_url: str = "redis://localhost:6379"

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket: str = ""

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    stripe_secret_key: str = ""

    whatsapp_api_token: str = ""

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
