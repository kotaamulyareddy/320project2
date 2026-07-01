"""
Configuration Management for API Gateway.

This module provides centralized configuration using Pydantic BaseSettings v2,
loading settings from environment variables with type validation and defaults.
Supports distinct profiles for development, staging, and production.
"""

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables with the same name.
    Nested settings (e.g., S3, PostgreSQL) use double underscore delimiting:
    e.g., S3__ENDPOINT_URL=http://localhost:9000
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------------------------
    # Application Meta
    # ---------------------------------------------------------------------
    APP_NAME: str = "Edge Video Analytics Gateway"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", description="Runtime environment: development, staging, production")
    DEBUG: bool = Field(default=True, description="Enable debug mode and verbose logging")
    API_V1_PREFIX: str = "/api/v1"

    # ---------------------------------------------------------------------
    # Server Configuration
    # ---------------------------------------------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = Field(default=1, description="Number of Uvicorn workers (production)")

    # ---------------------------------------------------------------------
    # Security & CORS
    # ---------------------------------------------------------------------
    SECRET_KEY: str = Field(
        default="super-secret-dev-key-change-in-production",
        description="JWT signing secret - MUST be overridden in production"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"],
        description="Allowed CORS origins for browser clients"
    )

    # ---------------------------------------------------------------------
    # PostgreSQL Database (via SQLAlchemy Async)
    # ---------------------------------------------------------------------
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_password"
    POSTGRES_DB: str = "edge_analytics"

    @property
    def DATABASE_URL(self) -> str:
        """Construct async SQLAlchemy database URL."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Construct synchronous database URL for Alembic migrations."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ---------------------------------------------------------------------
    # Redis Streams & Pub/Sub
    # ---------------------------------------------------------------------
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: float = 5.0
    REDIS_SOCKET_CONNECT_TIMEOUT: float = 5.0

    @property
    def REDIS_URL(self) -> str:
        """Construct Redis connection URL."""
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Stream Names
    RAW_FRAME_STREAM: str = "stream:raw_frames"
    PROCESSED_EVENT_STREAM: str = "stream:processed_events"
    ALERT_STREAM: str = "stream:alerts"
    TELEMETRY_STREAM: str = "stream:telemetry"

    # Consumer Groups
    VISION_PIPELINE_GROUP: str = "vision_pipeline_consumers"
    STREAM_PROCESSOR_GROUP: str = "stream_processor_consumers"
    WEBSOCKET_GATEWAY_GROUP: str = "websocket_gateway_consumers"

    # ---------------------------------------------------------------------
    # MinIO / S3 Object Storage
    # ---------------------------------------------------------------------
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "admin"
    S3_SECRET_KEY: str = "minio_password"
    S3_BUCKET_NAME: str = "anomaly-frames"
    S3_REGION: str = "us-east-1"
    S3_SECURE: bool = False  # Set True for HTTPS endpoints

    # ---------------------------------------------------------------------
    # Vision Pipeline & Model Configuration
    # ---------------------------------------------------------------------
    MODEL_PATH: str = "/models/yolov8n.onnx"
    MODEL_INPUT_WIDTH: int = 640
    MODEL_INPUT_HEIGHT: int = 640
    MODEL_CONFIDENCE_THRESHOLD: float = 0.5
    MODEL_IOU_THRESHOLD: float = 0.45
    USE_CUDA: bool = False
    INFERENCE_BATCH_SIZE: int = 4
    INFERENCE_NUM_THREADS: int = 0  # 0 = auto (all cores)

    # ---------------------------------------------------------------------
    # Video Stream Ingestion
    # ---------------------------------------------------------------------
    RTSP_STREAM_URL: str = "0"  # 0 = default webcam, or RTSP/HTTP URL
    FRAME_SKIP: int = 1  # Process every Nth frame
    MAX_FRAME_BUFFER_SIZE: int = 30
    JPEG_QUALITY: int = 85

    # ---------------------------------------------------------------------
    # WebSocket Configuration
    # ---------------------------------------------------------------------
    WS_HEARTBEAT_INTERVAL: int = 30  # seconds
    WS_MAX_MESSAGE_SIZE: int = 16 * 1024 * 1024  # 16 MB
    WS_COMPRESSION: bool = True

    # ---------------------------------------------------------------------
    # Metrics & Monitoring (Prometheus)
    # ---------------------------------------------------------------------
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    METRICS_PATH: str = "/metrics"

    # ---------------------------------------------------------------------
    # Logging
    # ---------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or console

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v.lower() not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v.lower()

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Cached settings instance.

    Using lru_cache ensures the configuration is parsed only once per process,
    which is critical for performance in high-throughput services.
    """
    return Settings()


# Global settings instance for easy import
settings = get_settings()