import uuid

from fastapi import HTTPException, status

from app.integrations.embeddings.local_client import EmbeddingsClient
from app.repositories.paper_repository import PaperRepository
from app.vectorstore.client import VectorStore


class SearchService:
    """Semantic search inside one paper's chunks.
    Scoped to a single paper on purpose, library-wide search is later"""

    def __init__(
        self,
        paper_repository: PaperRepository,
        embeddings_client: EmbeddingsClient,
        vector_store: VectorStore,
    ):
        self.paper_repository = paper_repository
        self.embeddings_client = embeddings_client
        self.vector_store = vector_store

    def search_within_paper(
        self, paper_id: uuid.UUID, *, owner_id: str, query: str, top_k: int = 5
    ) -> list[dict]:
        paper = self.paper_repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found")
        if paper.embedding_status != "embedded":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "This paper hasn't been embedded yet"
            )

        query_embedding = self.embeddings_client.embed_query(query)
        return self.vector_store.query_within_paper(
            owner_id=owner_id, paper_id=paper.id, query_embedding=query_embedding, top_k=top_k
        )
