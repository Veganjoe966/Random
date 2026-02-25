"""
Application configuration with environment variable loading.
All secrets loaded from environment — never hardcoded.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────
    app_name: str = "Hifdh Coach"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    # ── Database ─────────────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "hifdh"
    postgres_password: str = Field(default="changeme")
    postgres_db: str = "hifdh_coach"

    @computed_field
    @property
    def database_url(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    @computed_field
    @property
    def database_url_sync(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    # ── Redis ────────────────────────────────────────────────────────
    redis_url: RedisDsn = "redis://localhost:6379/0"  # type: ignore[assignment]
    redis_cache_ttl: int = 3600

    # ── Auth ─────────────────────────────────────────────────────────
    jwt_secret_key: str = Field(default="CHANGE-ME-IN-PRODUCTION")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # ── Object Storage (S3-compatible) ───────────────────────────────
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = Field(default="minioadmin")
    s3_secret_key: str = Field(default="minioadmin")
    s3_bucket_audio: str = "hifdh-audio"
    s3_bucket_exports: str = "hifdh-exports"
    s3_region: str = "us-east-1"

    # ── Stripe ───────────────────────────────────────────────────────
    stripe_secret_key: str = Field(default="sk_test_placeholder")
    stripe_publishable_key: str = Field(default="pk_test_placeholder")
    stripe_webhook_secret: str = Field(default="whsec_placeholder")

    # ── AI / Whisper ─────────────────────────────────────────────────
    whisper_model_size: str = "large-v3"
    whisper_device: str = "cuda"  # or "cpu"
    whisper_compute_type: str = "float16"
    max_audio_duration_seconds: int = 600  # 10 minutes
    max_audio_file_size_mb: int = 50

    # ── Celery ───────────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Encryption ───────────────────────────────────────────────────
    field_encryption_key: str = Field(default="CHANGE-ME-32-BYTE-KEY-HERE!!!!!")

    # ── Sentry ───────────────────────────────────────────────────────
    sentry_dsn: str = ""

    # ── Rate Limiting ────────────────────────────────────────────────
    rate_limit_per_minute: int = 60
    rate_limit_audio_upload_per_hour: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
