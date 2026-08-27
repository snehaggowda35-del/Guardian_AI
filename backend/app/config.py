from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore")
    database_url: str = "sqlite:///./guardian.db"
    jwt_secret: str = "development-only-change-me"
    demo_email: str = "parent@example.com"
    demo_password: str = "ChangeMe123!"
    allowed_origins: str = "http://127.0.0.1:8000,http://localhost:8000"
    environment: str = "development"
    ai_provider: str = "rules"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    ai_timeout_seconds: float = 10.0

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
