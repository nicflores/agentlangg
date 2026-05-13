from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_log_level: str = "INFO"

    db_provider: Literal["fake", "real"] = "fake"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "mcp_user"
    postgres_password: str = "mcp_password"
    postgres_db: str = "mcp_db"
    postgres_pool_min_size: int = 1
    postgres_pool_max_size: int = 10

    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000

    run_sql_default_limit: int = 100
    run_sql_max_rows: int = 1000
    run_sql_statement_timeout_ms: int = 5000
    run_sql_allowed_schemas: tuple[str, ...] = ("public",)


settings = Settings()
