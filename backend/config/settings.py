"""Application settings for the backend service.

Uses pydantic-settings so values can be overridden via environment variables
or a .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.config.openai_config import OpenAIConfig


class Settings(BaseSettings):
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "dev"  # dev | staging | prod

    # OpenAI configuration (raw env fields)
    OPENAI_API_KEY: str = ""
    OPENAI_ORG_ID: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_BATCH_SIZE: int = 100
    OPENAI_GENERATION_MODEL: str = "gpt-5-nano"
    OPENAI_TEMPERATURE: float = 0.3
    OPENAI_MAX_OUTPUT_TOKENS: int = 1000

    @property
    def openai_config(self) -> OpenAIConfig:
        """Return a validated OpenAIConfig built from the current environment."""

        return OpenAIConfig.from_env()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
