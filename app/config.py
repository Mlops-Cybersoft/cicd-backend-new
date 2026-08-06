from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "DocuMind Enterprise API"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]

    database_driver: str = "postgresql+psycopg"
    database_host: str = "localhost"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "documind"
    database_user: str = "documind"
    database_password: str = "documind"

    jwt_secret: str = "change-this-secret-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    seed_demo_data: bool = True
    demo_password: str = "ChangeMe123!"

    # Leave endpoint blank for Amazon S3. It only exists to support explicit
    # AWS-compatible endpoints in isolated test environments.
    s3_endpoint_url: str | None = None
    s3_region: str = "ap-southeast-1"
    s3_bucket: str = "documind-enterprise-documents"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_session_token: str | None = None
    s3_use_ssl: bool = True
    s3_presigned_expiry_seconds: int = 600
    max_upload_size_mb: int = 25

    embedding_provider: Literal["openai"] = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4.1-mini"
    rag_top_k: int = Field(default=6, ge=1, le=20)
    chunk_size: int = 900
    chunk_overlap: int = 120

    @property
    def database_url(self) -> URL:
        """Build a safely escaped SQLAlchemy URL from explicit DB settings."""
        return URL.create(
            drivername=self.database_driver,
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
