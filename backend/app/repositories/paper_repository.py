import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.paper import Paper
from app.models.tag import paper_tags

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
    
    def list_for_owner(self, owner_id: str, *, tag_id: uuid.UUID | None = None) -> list[Paper]:
        query = select(Paper).where(Paper.owner_id == owner_id)
        if tag_id is not None:
            query = query.join(paper_tags, Paper.id == paper_tags.c.paper_id).where(
                paper_tags.c.tag_id == tag_id
            )
        return list(self.db.scalars(query.order_by(Paper.created_at.desc())))

    def list_by_ids(self, paper_ids: list[uuid.UUID], *, owner_id: str) -> list[Paper]:
        #One query instead of N, and owner-scoped so a stray vector-store hit
        #can never surface another user's paper
        if not paper_ids:
            return []
        return list(
            self.db.scalars(
                select(Paper).where(Paper.id.in_(paper_ids), Paper.owner_id == owner_id)
            )
        )

    def attach_file(self, paper:Paper, *, storage_key: str, original_name: str, size_bytes: int) -> Paper:
        paper.file_storage_key = storage_key
        paper.file_original_name = original_name
        paper.file_size_bytes = size_bytes
        self.db.commit()
        self.db.refresh(paper)
        return paper

    def list_recently_opened(self, owner_id: str, *, limit: int = 4) -> list[Paper]:
        return list(
            self.db.scalars(
                select(Paper)
                .where(Paper.owner_id == owner_id, Paper.last_opened_at.is_not(None))
                .order_by(Paper.last_opened_at.desc())
                .limit(limit)
            )
        )

    def record_opened(self, paper: Paper, *, page: int | None) -> Paper:
        paper.last_opened_at = datetime.now(timezone.utc)
        if page is not None:
            paper.last_page = page
        self.db.commit()
        self.db.refresh(paper)
        return paper

    def set_suggested_questions(self, paper: Paper, questions_json: str) -> Paper:
        paper.suggested_questions = questions_json
        self.db.commit()
        self.db.refresh(paper)
        return paper

    def delete(self, paper: Paper) -> None:
        #Chunks, notes, tag and collection links all cascade at the FK level
        self.db.delete(paper)
        self.db.commit()

    def set_favorite(self, paper: Paper, is_favorite: bool) -> Paper:
        paper.is_favorite = is_favorite
        self.db.commit()
        self.db.refresh(paper)
        return paper

    def set_processing_status(self, paper: Paper, status: str) -> Paper:
        paper.processing_status = status
        self.db.commit()
        self.db.refresh(paper)
        return paper

    def set_embedding_status(self, paper: Paper, status: str) -> Paper:
        paper.embedding_status = status
        self.db.commit()
        self.db.refresh(paper)
        return paper