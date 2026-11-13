import os
import base64
from functools import lru_cache
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

try:
    from dotenv import load_dotenv
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH)
    else:
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
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://neondb_owner:npg_wGQXMY13UvyP@ep-silent-haze-b5t42cpv-pooler.c-7.us-east-2.aws.neon.tech/neondb?channel_binding=require&sslmode=require"
    )
    DATABASE_URL_UNPOOLED: Optional[str] = os.getenv(
        "DATABASE_URL_UNPOOLED",
        "postgresql://neondb_owner:npg_wGQXMY13UvyP@ep-silent-haze-b5t42cpv.c-7.us-east-2.aws.neon.tech/neondb?channel_binding=require&sslmode=require"
    )
    AUTO_CREATE_TABLES: bool = os.getenv("AUTO_CREATE_TABLES", "false").lower() in ("true", "1")

    # Neon Auth (Managed Better Auth / JWKS)
    NEON_AUTH_BASE_URL: str = os.getenv("NEON_AUTH_BASE_URL", "https://ep-silent-haze-b5t42cpv.neonauth.c-7.us-east-2.aws.neon.tech/neondb/auth")
    NEON_AUTH_JWKS_URL: str = os.getenv("NEON_AUTH_JWKS_URL", "https://ep-silent-haze-b5t42cpv.neonauth.c-7.us-east-2.aws.neon.tech/neondb/auth/.well-known/jwks.json")
    NEON_DATA_API_URL: str = os.getenv("NEON_DATA_API_URL", "")

    # Neon AI Gateway
    NEON_AI_GATEWAY_BASE_URL: str = os.getenv("NEON_AI_GATEWAY_BASE_URL", "")
    NEON_AI_GATEWAY_TOKEN: str = os.getenv("NEON_AI_GATEWAY_TOKEN", "")

    # Neon Object Storage (S3-compatible)
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "nak_live_cea36eea9c904dfbb4ca99a472f55d0f")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "nsk_live_71a0373bb684f4af73447ccdc80046d5a5bb7d4deeff7d4bc273269e767476d5")
    AWS_ENDPOINT_URL_S3: str = os.getenv("AWS_ENDPOINT_URL_S3", "https://br-still-boat-b5bl10k7.storage.c-7.us-east-2.aws.neon.tech")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-2")
    NEON_STORAGE_BUCKET: str = os.getenv("NEON_STORAGE_BUCKET", "assets")

    # Neon Realtime
    NEON_REALTIME_URL: str = os.getenv("NEON_REALTIME_URL", "wss://ep-silent-haze-b5t42cpv.rt.c-7.us-east-2.aws.neon.tech/")
    NEON_REALTIME_SECRET: str = os.getenv("NEON_REALTIME_SECRET", "nrt_live_1mL5BxJLukUlIqaF1m1UWQQh6oL9LPjE_czSpojd3mKE")

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
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@weschool-suez.edu.eg")

    # Gemini AI (quiz generation fallback)
    GEMINI_API_KEY: str = os.getenv(
        "GEMINI_API_KEY",
        base64.b64decode("QVEuQWI4Uk42Sy1XSERHaUw1MGdreGNTNzI3OW5yaFZlWUt4dnFXSmZyREh6Ykc0WTk3RWc=").decode("utf-8"),
    )

    if HAS_PYDANTIC_SETTINGS and SettingsConfigDict is not None:
        model_config = SettingsConfigDict(
            env_file=str(ENV_PATH) if ENV_PATH.exists() else ".env",
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
