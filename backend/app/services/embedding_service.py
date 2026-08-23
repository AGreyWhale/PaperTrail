import uuid
from typing import Callable

from fastapi import HTTPException, status

from app.repositories.chunk_repository import ChunkRepository
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import PaperOut


class EmbeddingService:
    """Validates a paper is eligible to embed, marks it queued, and hands
    the work off. The model never runs here, this is inside the request.

    enqueue_fn is injected instead of importing the Celery task so tests
    don't need a live broker"""

    def __init__(
        self,
        paper_repository: PaperRepository,
        chunk_repository: ChunkRepository,
        enqueue_fn: Callable[[str, str], None],
    ):
        self.paper_repository = paper_repository
        self.chunk_repository = chunk_repository
        self._enqueue_fn = enqueue_fn

    def enqueue_embedding(self, paper_id: uuid.UUID, *, owner_id: str) -> PaperOut:
        paper = self.paper_repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found")
        if paper.processing_status != "processed":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "This paper must be processed into chunks before it can be embedded",
            )
        if not self.chunk_repository.list_for_paper(paper.id):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "This paper has no chunks to embed"
            )

        #Clears any previous error, so the retry path and the first attempt
        #are the same code — nothing separate to keep in sync
        paper = self.paper_repository.set_embedding_status(paper, "queued")
        self._enqueue_fn(str(paper.id), owner_id)
        return PaperOut.from_model(paper)
