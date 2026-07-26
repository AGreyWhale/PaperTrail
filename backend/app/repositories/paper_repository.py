import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.paper import Paper

class PaperRepository:
    #Owns all database acess for Paper in case we switch from Postgres

    def __init__(self, db:Session):
        self.db = db
    
    def create(self, *, owner_id: str, title: str, authors: str, venue: str | None, year: int | None) -> Paper:
        paper = Paper(owner_id=owner_id, title=title, authors=authors, venue=venue, year=year)
        self.db.add(paper)
        self.db.commit()
        self.db.refresh(paper)
        return paper
    
    def get(self, paper_id: uuid.UUID, *, owner_id: str) -> Paper | None:
        paper = self.db.get(Paper, paper_id)
        return paper if paper and paper.owner_id == owner_id else None
    
    def list_for_owner(self, owner_id: str) -> list[Paper]:
        return list(
            self.db.scalars(
                select(Paper).where(Paper.owner_id == owner_id).order_by(Paper.created_at.desc())
            )
        )

    def attach_file(self, paper:Paper, *, storage_key: str, original_name: str, size_bytes: int) -> Paper:
        paper.file_storage_key = storage_key
        paper.file_original_name = original_name
        paper.file_size_bytes = size_bytes
        self.db.commit()
        self.db.refresh(paper)
        return paper

    def set_processing_status(self, paper: Paper, status: str) -> Paper:
        paper.processing_status = status
        self.db.commit()
        self.db.refresh(paper)
        return paper