from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    database_url: str = "postgresql://user:password@localhost:5432/url_shortener"
    redis_url: str = "redis://localhost:6379"
    base_url: str = "http://localhost:8000"

    # DynamoDB
    dynamo_region: str = "us-east-1"
    dynamo_table: str = "url_shortener"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
