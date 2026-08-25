import uuid

from sqlalchemy.orm import Session

from app.integrations.embeddings.local_client import EmbeddingsClient
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.paper_repository import PaperRepository


def run_embedding_job(
    paper_id: uuid.UUID,
    *,
    owner_id: str,
    db: Session,
    embeddings_client: EmbeddingsClient,
) -> None:
    #Fetches a paper's chunks, embeds them, writes the vectors back onto the
    #chunk rows. Everything is injected, so tests call this with fakes
    paper_repository = PaperRepository(db)
    chunk_repository = ChunkRepository(db)

    paper = paper_repository.get(paper_id, owner_id=owner_id)
    if paper is None:
        # Deleted after the job was queued, nothing to do.
        return

    paper_repository.set_embedding_status(paper, "embedding")

    try:
        chunks = chunk_repository.list_for_paper(paper.id)
        embeddings = embeddings_client.embed_documents([c.text for c in chunks])

        # Marking a paper "embedded" when nothing was actually written leaves it
        # claiming to be searchable while every query returns nothing — which is
        # exactly how a stale worker silently broke a whole library once.
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"embedder returned {len(embeddings)} vectors for {len(chunks)} chunks"
            )

        chunk_repository.store_embeddings(list(zip([c.id for c in chunks], embeddings)))

        stored = chunk_repository.count_embedded_for_paper(paper.id)
        if stored != len(chunks):
            raise RuntimeError(f"only {stored} of {len(chunks)} chunks have vectors after storing")
    except Exception as exc:
        #Record why, not just that it failed
        paper_repository.set_embedding_status(paper, "failed", error=f"{type(exc).__name__}: {exc}")
        raise

    paper_repository.set_embedding_status(paper, "embedded")
