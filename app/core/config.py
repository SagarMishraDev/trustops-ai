"""Application configuration.

WHAT: Central settings for TrustOps AI.
WHY:  Secrets and environment-specific values must never be hard-coded.
      Everything is read from environment variables / a local .env file.
HOW:  pydantic-settings reads .env automatically. Defaults are safe for
      local development only (SQLite, mock LLM provider).
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TrustOps AI"
    app_version: str = "0.1.0"
    environment: str = "development"  # development | production
    debug: bool = True

    # Database - SQLite for MVP, PostgreSQL-ready via DATABASE_URL
    database_url: str = "sqlite:///./data/trustops.db"

    # Security - CHANGE these in your real .env, never commit real values
    secret_key: str = "change-me-in-env"
    api_key_header: str = "X-API-Key"

    # LLM provider - configurable, NOT locked to one vendor
    llm_provider: str = "mock"  # mock | openai | anthropic | inception (Phase 3 wires the real chain)
    llm_model: str = "mock-evaluator-v1"
    llm_api_key: str = ""  # set via .env only: LLM_API_KEY
    llm_temperature: float = 0.0
    llm_base_url: str = ""  # for OpenAI-compatible providers (e.g. Inception/Mercury)
    # Rough per-1K-token USD rates used ONLY for cost estimates (labelled estimates, not billing)
    llm_input_cost_per_1k: float = 0.001
    llm_output_cost_per_1k: float = 0.002

    # Uploads (Phase 2 enforces these)
    max_upload_size_mb: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
