import logging
import time
import uuid

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.integrations.embeddings.local_client import EmbeddingsClient
from app.workers.celery_app import celery_app
from app.storage.factory import build_file_storage
from app.workers.embedding_job import run_embedding_job
from app.workers.prepare_job import run_prepare_job

logger = logging.getLogger(__name__)


def embed_paper_now(paper_id: str, owner_id: str) -> None:
    #The one place real dependencies get wired up. Both the Celery task and the
    #BackgroundTasks fallback call this, so the two paths can't drift apart.
    #Opens its own session on purpose: this runs outside the request, either in
    #a worker process or after the response has already been sent
    settings = get_settings()
    db = SessionLocal()
    try:
        run_embedding_job(
            uuid.UUID(paper_id),
            owner_id=owner_id,
            db=db,
            embeddings_client=EmbeddingsClient(model_name=settings.embedding_model),
        )
    finally:
        db.close()


@celery_app.task(name="embed_paper")
def embed_paper_task(paper_id: str, owner_id: str) -> None:
    embed_paper_now(paper_id, owner_id)


def prepare_paper_now(paper_id: str, owner_id: str) -> None:
    #Parse + embed in one go. Same wiring shape as embed_paper_now: its own
    #session, real dependencies built here, logic left to the job function.
    #
    #Logged at every step on purpose. This runs detached from the request, so
    #when the process is killed mid-job — OOM, or a free-tier instance spinning
    #down — nothing is raised and nothing is written: the paper just sits on
    #"processing" forever. The log is the only way to see how far it got.
    settings = get_settings()
    started = time.monotonic()
    logger.info("prepare: starting paper=%s backend=%s", paper_id, settings.embedding_backend)

    db = SessionLocal()
    try:
        run_prepare_job(
            uuid.UUID(paper_id),
            owner_id=owner_id,
            db=db,
            storage=build_file_storage(settings),
            embeddings_client=EmbeddingsClient(model_name=settings.embedding_model),
        )
        logger.info("prepare: finished paper=%s in %.1fs", paper_id, time.monotonic() - started)
    except Exception:
        #run_prepare_job already recorded the reason on the paper; this makes it
        #visible in the platform log too, where it would otherwise be swallowed
        logger.exception("prepare: FAILED paper=%s after %.1fs", paper_id, time.monotonic() - started)
        raise
    finally:
        db.close()


@celery_app.task(name="prepare_paper")
def prepare_paper_task(paper_id: str, owner_id: str) -> None:
    prepare_paper_now(paper_id, owner_id)
