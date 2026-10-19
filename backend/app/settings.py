import os
from functools import lru_cache
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core
    ENVIRONMENT: str = "local"
    LOG_LEVEL: str = "INFO"

    # PostgreSQL
    DATABASE_URL: str = "postgresql://mrinal@localhost:5432/loan_engine"
    TEST_DATABASE_URL: str = "postgresql://mrinal@localhost:5432/loan_engine_test"

    # AWS
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET_NAME: str = "loan-eligibility-uploads-local"
    SQS_QUEUE_URL: Optional[str] = None
    SQS_DLQ_URL: Optional[str] = None

    # Ingestion constraints
    MAX_FILE_SIZE_BYTES: int = 104_857_600  # 100 MB
    PRESIGNED_URL_EXPIRATION_SECONDS: int = 900  # 15 mins
    ALLOWED_EXTENSIONS: List[str] = [".csv"]
    ALLOWED_MIME_TYPES: List[str] = [
        "text/csv",
        "application/csv",
        "text/plain",
        "application/vnd.ms-excel"
    ]

    # Email notification safety
    DELIVERY_MODE: str = "test"  # 'test' or 'production'
    ALLOW_REAL_RECIPIENTS: bool = False
    TEST_EMAIL_RECIPIENTS: str = "developer-test-inbox@example.com"
    SES_FROM_EMAIL: str = "no-reply@verified-domain.com"

    # Security
    WEBHOOK_SECRET: str = "replace-with-a-secure-random-64-char-token"

    # n8n Workflow Webhooks
    N8N_MATCHING_WEBHOOK_URL: str = "http://localhost:5678/webhook/user-loan-matching"
    N8N_NOTIFICATION_WEBHOOK_URL: str = "http://localhost:5678/webhook/user-notification"

    # LLM Configuration
    LLM_PROVIDER: str = "mock"  # mock | openai | gemini
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: int = 10
    LLM_MAX_TOKENS: int = 500

    @property
    def test_recipient_list(self) -> List[str]:
        return [e.strip() for e in self.TEST_EMAIL_RECIPIENTS.split(",") if e.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
