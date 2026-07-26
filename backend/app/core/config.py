from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    #Central app config
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "PaperTrail API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg2://papertrail:papertrail@localhost:5432/papertrail"

    
    # Both spellings of the Vite dev server: CORS compares Origin as an
    # exact string, so localhost and 127.0.0.1 are distinct origins even
    # though they resolve to the same host.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    openai_api_key: str = ""

    clerk_secret_key: str = ""
    clerk_authorized_parties: str = "http://localhost:5173,http://127.0.0.1:5173"
    
    crossref_contact_email: str = ""
    
    local_storage_root: str = "./storage"
    max_upload_size_mb: int = 50

    @property
    def clerk_authorized_parties_list(self) -> list[str]:
        return [p.strip() for p in self.clerk_authorized_parties.split(",") if p.strip()]
    
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