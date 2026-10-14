"""Media Worker configuration via pydantic-settings."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Centralized settings for the media-worker."""

    # ──── Object Storage (MinIO / Arvan S3) ────
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "content-repurposing"
    S3_REGION: str = "us-east-1"

    # ──── Database ────
    DATABASE_URL: str = "postgresql://app:changeme_in_production@postgres:5432/content_repurposing"

    # ──── Redis ────
    REDIS_URL: str = "redis://redis:6379/0"

    # ──── AI Providers ────
    AVALAI_API_KEY: str = ""
    AVALAI_BASE_URL: str = "https://api.avalai.ir/v1"
    AVALAI_STT_MODEL: str = "gpt-4o-transcribe"

    OPENAI_API_KEY: str = ""

    STT_PROVIDER: str = "avalai"
    SHENAVA_MODEL_PATH: str = "/app/models/shenava-koochik"

    # ──── Processing ────
    TEMP_DIR: str = "/tmp/media"
    MAX_STT_FILE_SIZE_MB: int = 25  # AvalAI/OpenAI limit
    CANONICAL_SAMPLE_RATE: int = 16000
    CANONICAL_CHANNELS: int = 1  # Mono
    CHUNK_DURATION_SECONDS: int = 180  # 3 min chunks for better local memory stability
    
    # ──── Webhooks ────
    N8N_TRANSCRIPTION_COMPLETED_WEBHOOK_URL: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
