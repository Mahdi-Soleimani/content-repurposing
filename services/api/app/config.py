"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://app:changeme_in_production@postgres:5432/content_repurposing"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # API
    API_SECRET_KEY: str = "change-this-secret-key-in-production"
    API_DEBUG: bool = True
    API_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost"

    # Object Storage (S3 / MinIO)
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "content-repurposing"
    S3_REGION: str = "us-east-1"
    S3_PUBLIC_URL: str = "http://localhost:9000"

    # n8n
    N8N_URL: str = "http://n8n:5678"
    N8N_WEBHOOK_URL: str = "http://n8n:5678/webhook/content-uploaded"
    N8N_GENERATION_WEBHOOK_URL: str | None = None

    # Media Worker
    MEDIA_WORKER_URL: str = "http://media-worker:8001"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.API_ALLOWED_ORIGINS.split(",")]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
