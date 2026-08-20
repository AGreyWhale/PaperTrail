import uuid

import chromadb

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.integrations.embeddings.local_client import EmbeddingsClient
from app.vectorstore.client import VectorStore
from app.workers.celery_app import celery_app
from app.workers.embedding_job import run_embedding_job


@celery_app.task(name="embed_paper")
def embed_paper_task(paper_id: str, owner_id: str) -> None:
    #Runs in a worker process, not the API. Only job is building the real
    #dependencies and handing off, so it stays trivially correct
    settings = get_settings()
    db = SessionLocal()
    try:
        embeddings_client = EmbeddingsClient(model_name=settings.embedding_model)
        chroma_client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)

        run_embedding_job(
            uuid.UUID(paper_id),
            owner_id=owner_id,
            db=db,
            embeddings_client=embeddings_client,
            vector_store=VectorStore(chroma_client),
        )
    finally:
        db.close()
