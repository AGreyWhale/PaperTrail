from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    #Central app config
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "PaperTrail API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg2://papertrail:papertrail@localhost:5432/papertrail"

    
    cors_origins: str = "http://localhost:5173"

    openai_api_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """
    Cached so Settings is only constructed once per process, and so it
    can be swapped via FastAPI's dependency-override system in tests.
    """
    return Settings()