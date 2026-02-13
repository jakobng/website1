from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Field Translator"
    environment: str = "dev"
    db_path: str = "field_translator.db"

    provider: str = "mock"  # mock | openai

    openai_api_key: str | None = None
    openai_transcribe_model: str = "gpt-4o-transcribe"
    openai_translate_model: str = "gpt-4.1-mini"

    max_context_lines: int = 4
    segment_timeout_seconds: int = 45
    cors_allow_origins: str = "*"

    model_config = SettingsConfigDict(
        env_prefix="FT_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()