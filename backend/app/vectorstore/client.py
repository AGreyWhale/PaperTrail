import uuid

import chromadb

_COLLECTION_NAME = "paper_chunks"

class VectorStore:
    """Wraps a chroma collection for storing and querying chunk embeddings.
    Only change this file if vector db changes"""

    def __init__(self, client: chromadb.ClientAPI):
        self._collection = client.get_or_create_collection(
            _COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
    
    def upsert_chunks(self, *, owner_id: str, paper_id: uuid.UUID, chunk_ids: list[uuid.UUID], texts: list[str], embeddings: list[list[float]], page_numbers: list[int]) -> None:
        if not chunk_ids:
            return
        self._collection.upsert(
            ids=[str(cid) for cid in chunk_ids],
            embeddings=embeddings,
            documents=texts,
            metadatas=[
                {"owner_id": owner_id, "paper_id": str(paper_id), "page_number": page}
                for page in page_numbers
            ],
        )
    
    def delete_for_paper(self, paper_id: uuid.UUID) -> None:
        self._collection.delete(where={"paper_id": str(paper_id)})
    
    def query_within_paper(
        self, *, owner_id: str, paper_id: uuid.UUID, query_embedding: list[float], top_k: int = 5
    ) -> list[dict]:
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={
                "$and": [
                    {"paper_id": {"$eq": str(paper_id)}},
                    {"owner_id": {"$eq": owner_id}},
                ]
            },
        )

        # Chroma nests one list per submitted query embedding, and we only
        # ever send one, so everything we want lives at index 0. No matches
        # comes back as empty inner lists rather than a missing key.
        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        return [
            {
                "chunk_id": uuid.UUID(chunk_id),
                "text": documents[i],
                "page_number": metadatas[i]["page_number"],
                # The collection is cosine space, so distance is 1 - similarity.
                # Callers want "higher is better", so flip it back here.
                "score": 1.0 - distances[i],
            }
            for i, chunk_id in enumerate(ids)
        ]