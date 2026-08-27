import logging
import uuid

from sqlalchemy.orm import Session

from app.chunking.chunker import chunk_pages
from app.integrations.embeddings.local_client import EmbeddingsClient
from app.parsing.pdf_parser import extract_pages
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.paper_repository import PaperRepository
from app.storage.base import FileStorage
from app.workers.embedding_job import run_embedding_job

logger = logging.getLogger(__name__)


def run_prepare_job(
    paper_id: uuid.UUID,
    *,
    owner_id: str,
    db: Session,
    storage: FileStorage,
    embeddings_client: EmbeddingsClient,
) -> None:
    """
    Parse -> chunk -> embed, as one unit. These were two endpoints the reader
    had to press in order, which is an implementation detail leaking into the
    UI: a paper is either ready for questions or it isn't.

    Everything is injected, so tests drive it with fakes and no Celery.
    """
    paper_repository = PaperRepository(db)
    chunk_repository = ChunkRepository(db)

    paper = paper_repository.get(paper_id, owner_id=owner_id)
    if paper is None:
        # Deleted after the job was queued, nothing to do.
        return
    if paper.file_storage_key is None:
        paper_repository.set_processing_status(paper, "failed")
        paper_repository.set_embedding_status(paper, "failed", error="No file attached to process")
        return

    paper_repository.set_processing_status(paper, "processing")
    try:
        logger.info("prepare: downloading pdf paper=%s", paper_id)
        content = storage.read(key=paper.file_storage_key)
        logger.info("prepare: parsing %d bytes paper=%s", len(content), paper_id)
        chunks = chunk_pages(extract_pages(content))
        logger.info("prepare: %d chunks paper=%s", len(chunks), paper_id)
        if not chunks:
            #A PDF that yields nothing usable is a failure, not a paper that's
            #ready with zero content
            raise RuntimeError("no usable text could be extracted from this PDF")
        chunk_repository.replace_all_for_paper(paper.id, chunks)
    except Exception as exc:
        paper_repository.set_processing_status(paper, "failed")
        paper_repository.set_embedding_status(
            paper, "failed", error=f"{type(exc).__name__}: {exc}"
        )
        raise

    paper_repository.set_processing_status(paper, "processed")

    logger.info("prepare: embedding %d chunks paper=%s", len(chunks), paper_id)
    #Embedding owns its own status transitions and error recording
    run_embedding_job(paper.id, owner_id=owner_id, db=db, embeddings_client=embeddings_client)
