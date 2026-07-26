import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.chunking.chunker import ChunkResult
from app.models.chunk import Chunk

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