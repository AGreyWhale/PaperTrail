import uuid

from sqlalchemy import bindparam, delete, func, select, update
from sqlalchemy.orm import Session

from app.chunking.chunker import ChunkResult
from app.models.chunk import Chunk
from app.models.paper import Paper

class ChunkRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def replace_all_for_paper(self, paper_id: uuid.UUID, chunks: list[ChunkResult]) -> list[Chunk]:
        #Deletes existing chunks for paper and inserts new set
        self.db.execute(delete(Chunk).where(Chunk.paper_id == paper_id))

        rows = [
            Chunk(
                paper_id=paper_id,
                chunk_index=c.chunk_index,
                page_number=c.page_number,
                text=c.text,
                token_count=c.token_count
            )
            for c in chunks
        ]
        self.db.add_all(rows)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows
    
    def list_for_paper(self, paper_id: uuid.UUID) -> list[Chunk]:
        return list(
            self.db.scalars(
                select(Chunk).where(Chunk.paper_id == paper_id).order_by(Chunk.chunk_index)
            )
        )
    def store_embeddings(self, pairs: list[tuple[uuid.UUID, list[float]]]) -> None:
        #Embeddings live on the chunk row, so this updates rows the chunking
        #stage already created rather than inserting into a separate store
        if not pairs:
            return
        for chunk_id, embedding in pairs:
            self.db.execute(
                update(Chunk).where(Chunk.id == chunk_id).values(embedding=embedding)
            )
        self.db.commit()

    def count_embedded_for_paper(self, paper_id: uuid.UUID) -> int:
        #Used to verify a job really wrote vectors before it claims success
        return self.db.scalar(
            select(func.count(Chunk.id)).where(
                Chunk.paper_id == paper_id, Chunk.embedding.is_not(None)
            )
        ) or 0

    def find_similar_within_paper(
        self, paper_id: uuid.UUID, *, owner_id: str, query_embedding: list[float], top_k: int = 5
    ) -> list[dict]:
        #owner_id is joined in as defence in depth. Callers already check
        #ownership; this makes a query that returns someone else's chunk
        #impossible rather than merely unlikely
        rows = self.db.execute(
            self._similarity_query(query_embedding, top_k).where(Chunk.paper_id == paper_id),
            {"owner_id": owner_id},
        ).all()
        return [_as_match(row) for row in rows]

    def find_similar_for_owner(
        self,
        *,
        owner_id: str,
        query_embedding: list[float],
        top_k: int = 20,
        paper_ids: list[uuid.UUID] | None = None,
    ) -> list[dict]:
        #Every embedded chunk this owner has, or just the given papers when the
        #caller is scoping to a selection. Carries paper_id for grouping
        query = self._similarity_query(query_embedding, top_k)
        if paper_ids is not None:
            query = query.where(Chunk.paper_id.in_(paper_ids))

        rows = self.db.execute(query, {"owner_id": owner_id}).all()
        return [_as_match(row, with_paper_id=True) for row in rows]

    @staticmethod
    def _similarity_query(query_embedding: list[float], top_k: int):
        distance = Chunk.embedding.cosine_distance(query_embedding)
        return (
            select(Chunk.id, Chunk.paper_id, Chunk.text, Chunk.page_number, distance.label("distance"))
            .join(Paper, Paper.id == Chunk.paper_id)
            .where(Paper.owner_id == bindparam("owner_id"))
            # Rows that were never embedded would otherwise sort as NULL-distance
            .where(Chunk.embedding.is_not(None))
            .order_by(distance)
            .limit(top_k)
        )


def _as_match(row, *, with_paper_id: bool = False) -> dict:
    match = {
        "chunk_id": row.id,
        "text": row.text,
        "page_number": row.page_number,
        # Cosine distance is 1 - similarity; callers want "higher is better".
        "score": 1.0 - row.distance,
    }
    if with_paper_id:
        match["paper_id"] = row.paper_id
    return match
