import os
from functools import lru_cache
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    HAS_PYDANTIC_SETTINGS = True
except ImportError:
    from pydantic import BaseModel as BaseSettings
    SettingsConfigDict = None
    HAS_PYDANTIC_SETTINGS = False

OTP_EXPIRE_MINUTES = 10


class Settings(BaseSettings):
    # App
    APP_NAME: str = os.getenv("APP_NAME", "WE School Suez Tawasol")
    APP_VERSION: str = os.getenv("APP_VERSION", "2.0.0")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1")

    # Database (PostgreSQL / Neon)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/we_tawasol?sslmode=require")
    DATABASE_URL_UNPOOLED: Optional[str] = os.getenv("DATABASE_URL_UNPOOLED")
    AUTO_CREATE_TABLES: bool = os.getenv("AUTO_CREATE_TABLES", "false").lower() in ("true", "1")

    # Neon Auth (Managed Better Auth / JWKS)
    NEON_AUTH_BASE_URL: str = os.getenv("NEON_AUTH_BASE_URL", "")
    NEON_AUTH_JWKS_URL: str = os.getenv("NEON_AUTH_JWKS_URL", "")
    NEON_DATA_API_URL: str = os.getenv("NEON_DATA_API_URL", "")

    # Neon AI Gateway
    NEON_AI_GATEWAY_BASE_URL: str = os.getenv("NEON_AI_GATEWAY_BASE_URL", "")
    NEON_AI_GATEWAY_TOKEN: str = os.getenv("NEON_AI_GATEWAY_TOKEN", "")

    # Neon Object Storage (S3-compatible)
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_ENDPOINT_URL_S3: str = os.getenv("AWS_ENDPOINT_URL_S3", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-2")
    NEON_STORAGE_BUCKET: str = os.getenv("NEON_STORAGE_BUCKET", "assets")

    # Neon Realtime
    NEON_REALTIME_URL: str = os.getenv("NEON_REALTIME_URL", "")
    NEON_REALTIME_SECRET: str = os.getenv("NEON_REALTIME_SECRET", "")

    # Neon Functions
    NEON_FUNCTION_HELLO_BASE_URL: str = os.getenv("NEON_FUNCTION_HELLO_BASE_URL", "")

    # JWT (Local fallback or signing)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-to-a-very-long-random-secret-key-min-32-chars")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    RESET_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "5"))

    # SMTP email
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "")

    # Gemini AI (quiz generation fallback)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    if HAS_PYDANTIC_SETTINGS and SettingsConfigDict is not None:
        model_config = SettingsConfigDict(
            env_file=".env",
            extra="ignore",
            case_sensitive=False,
        )
    else:
        class Config:
            extra = "ignore"
            case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
