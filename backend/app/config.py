"""Application settings, loaded from environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "ksp"
    postgres_password: str = "ksp_local_dev"
    postgres_db: str = "ksp_crime"
    postgres_host: str = "db"
    postgres_port: int = 5432

    anthropic_api_key: str = ""
    orchestration_model: str = "claude-opus-4-8"
    bulk_model: str = "claude-sonnet-5"

    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
