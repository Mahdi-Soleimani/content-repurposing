"""Source Worker configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Settings for source-worker."""
    
    # ──── Object Storage ────
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "content-repurposing"
    S3_REGION: str = "us-east-1"

    # ──── Database ────
    DATABASE_URL: str = "postgresql://app:changeme_in_production@postgres:5432/content_repurposing"

    # ──── Redis ────
    REDIS_URL: str = "redis://redis:6379/0"

    # ──── Services ────
    MEDIA_WORKER_URL: str = "http://media-worker:8001"

    # ──── Download Settings ────
    DOWNLOAD_TEMP_DIR: str = "/tmp/downloads"
    DOWNLOAD_MIN_DELAY: int = 10
    DOWNLOAD_MAX_DELAY: int = 30
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
