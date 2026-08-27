import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import collections, health, notes, papers, search, synthesis, tags
from app.core.config import get_settings
from app.storage.supabase_storage import StorageNotConfiguredError

#uvicorn configures its own loggers but leaves the root logger alone, so
#application INFO records were being dropped before reaching the platform log.
#That is why a background job could die mid-run and show nothing at all.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    force=True,
)

logger = logging.getLogger(__name__)

settings = get_settings()


def _warn_if_storage_misconfigured() -> None:
    #Surfaces at boot in the deploy log, instead of on the first upload attempt
    if settings.storage_backend != "supabase":
        return
    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", settings.supabase_url),
            ("SUPABASE_SERVICE_ROLE_KEY", settings.supabase_service_role_key),
            ("SUPABASE_STORAGE_BUCKET", settings.supabase_storage_bucket),
        )
        if not value
    ]
    if missing:
        logger.error(
            "STORAGE_BACKEND=supabase but %s not set — file uploads and reads will fail",
            ", ".join(missing),
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _warn_if_storage_misconfigured()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(StorageNotConfiguredError)
def _storage_not_configured(_request: Request, exc: StorageNotConfiguredError) -> JSONResponse:
    #A deployment problem, not a client one — 503 with the missing variable
    #named, rather than a stack trace the user can do nothing with
    return JSONResponse(status_code=503, content={"detail": str(exc)})


app.include_router(health.router)
app.include_router(papers.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(tags.router, prefix="/api")
app.include_router(collections.router, prefix="/api")
app.include_router(notes.router, prefix="/api")
app.include_router(synthesis.router, prefix="/api")