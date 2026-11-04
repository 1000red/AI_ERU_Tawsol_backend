from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional

OTP_EXPIRE_MINUTES = 10


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ERU Tawasol"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # Database (PostgreSQL / Neon)
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/eru_tawasol?sslmode=require"
    DATABASE_URL_UNPOOLED: Optional[str] = None

    # Neon Auth (Managed Better Auth / JWKS)
    NEON_AUTH_BASE_URL: str = ""
    NEON_AUTH_JWKS_URL: str = ""
    NEON_DATA_API_URL: str = ""

    # Neon AI Gateway
    NEON_AI_GATEWAY_BASE_URL: str = ""
    NEON_AI_GATEWAY_TOKEN: str = ""

    # Neon Object Storage (S3-compatible)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_ENDPOINT_URL_S3: str = ""
    AWS_REGION: str = "us-east-2"
    NEON_STORAGE_BUCKET: str = "assets"

    # Neon Realtime
    NEON_REALTIME_URL: str = ""
    NEON_REALTIME_SECRET: str = ""

    # Neon Functions
    NEON_FUNCTION_HELLO_BASE_URL: str = ""

    # JWT (Local fallback or signing)
    SECRET_KEY: str = "change-this-to-a-very-long-random-secret-key-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440   # 24h
    RESET_TOKEN_EXPIRE_MINUTES: int = 5

    # SMTP email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""

    # Gemini AI (quiz generation fallback)
    GEMINI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
