"""Application settings for the backend service.

Uses pydantic-settings so values can be overridden via environment variables
or a .env file in later stories.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "dev"  # dev | staging | prod

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
