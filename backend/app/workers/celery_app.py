from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "papertrail",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    # Without this the worker starts with no tasks registered and
    # rejects every embed_paper message as unknown.
    include=["app.workers.tasks"],
)
