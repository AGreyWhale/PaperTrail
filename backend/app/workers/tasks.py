import uuid

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.integrations.embeddings.local_client import EmbeddingsClient
from app.workers.celery_app import celery_app
from app.workers.embedding_job import run_embedding_job


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
