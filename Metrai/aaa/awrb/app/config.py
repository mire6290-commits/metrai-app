import os
from typing import List, Union
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Metrai Calculus"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Database Settings
    DATABASE_URL: str = "sqlite:///./metrai_calculus.db"

    # Security & Limits
    ALLOWED_HOSTS: str = "*"
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    CSRF_COOKIE_SECURE: bool = True
    SESSION_COOKIE_SECURE: bool = True

    # OCR Settings
    TESSERACT_CMD: str = ""

    # SMTP / Verification Setup
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@metraicalculus.com"

    # Cache Settings
    CACHE_TTL_SECONDS: int = 300

    @property
    def cors_origins(self) -> List[str]:
        if self.ALLOWED_HOSTS == "*":
            return ["*"]
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",")]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
