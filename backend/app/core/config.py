from functools import lru_cache
from typing import Literal

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

    # Any OpenAI-compatible endpoint works, so switching providers
    # (Gemini, Together, a local Ollama) is these three values, not code.
    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-120b"

    clerk_secret_key: str = ""
    clerk_authorized_parties: str = "http://localhost:5173,http://127.0.0.1:5173"

    crossref_contact_email: str = ""

    local_storage_root: str = "./storage"
    max_upload_size_mb: int = 50

    # Embeddings run locally via sentence-transformers, so no key here.
    # Vectors live in Postgres via pgvector — no separate vector service.
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # "celery" needs a worker process and Redis; "background_tasks" runs the
    # job in-process after the response, which is what free tiers can host.
    embedding_backend: Literal["celery", "background_tasks"] = "celery"

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

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