import uuid

from sqlalchemy.orm import Session

from app.integrations.embeddings.local_client import EmbeddingsClient
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.paper_repository import PaperRepository
from app.vectorstore.client import VectorStore


def run_embedding_job(
    paper_id: uuid.UUID,
    *,
    owner_id: str,
    db: Session,
    embeddings_client: EmbeddingsClient,
    vector_store: VectorStore,
) -> None:
    #Fetches a paper's chunks, embeds them, stores the vectors.
    #Everything is injected, so tests call this with fakes and no Celery
    paper_repository = PaperRepository(db)
    chunk_repository = ChunkRepository(db)

    paper = paper_repository.get(paper_id, owner_id=owner_id)
    if paper is None:
        # Deleted after the job was queued, nothing to do.
        return

    paper_repository.set_embedding_status(paper, "embedding")

    try:
        chunks = chunk_repository.list_for_paper(paper.id)
        texts = [c.text for c in chunks]
        embeddings = embeddings_client.embed_documents(texts)

        vector_store.upsert_chunks(
            owner_id=owner_id,
            paper_id=paper.id,
            chunk_ids=[c.id for c in chunks],
            texts=texts,
            embeddings=embeddings,
            page_numbers=[c.page_number for c in chunks],
        )
    except Exception:
        paper_repository.set_embedding_status(paper, "failed")
        raise

    paper_repository.set_embedding_status(paper, "embedded")
