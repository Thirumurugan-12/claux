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

    # --- LLM provider selection ---------------------------------------------
    # "uniai" (default): Zoho Catalyst UniAI / any OpenAI-compatible gateway — the
    # hackathon path: paste the key issued in the Catalyst console and go.
    # "anthropic": direct Anthropic SDK (claude-opus-4-8).
    llm_provider: str = "uniai"

    # Catalyst UniAI / OpenAI-compatible gateway (BYOK from the Catalyst console)
    uniai_base_url: str = ""
    uniai_api_key: str = ""
    uniai_model: str = ""
    uniai_chat_path: str = "/v1/chat/completions"
    uniai_auth_scheme: str = "bearer"  # or "zoho-oauthtoken"

    # Direct Anthropic path
    anthropic_api_key: str = ""
    orchestration_model: str = "claude-opus-4-8"
    bulk_model: str = "claude-sonnet-5"

    # Comma-separated allowed origins — add the Catalyst Slate domain in production,
    # e.g. "https://<project>.catalystserverless.com"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

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
