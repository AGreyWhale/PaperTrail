import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.note import Note

class NoteRepository:
    #Owns all database access for Note

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        paper_id: uuid.UUID,
        owner_id: str,
        content: str,
        quoted_text: str | None,
        page_number: int | None,
        color: str | None = None,
    ) -> Note:
        note = Note(
            paper_id=paper_id,
            owner_id=owner_id,
            content=content,
            quoted_text=quoted_text,
            page_number=page_number,
            color=color,
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def get(self, note_id: uuid.UUID, *, owner_id: str) -> Note | None:
        note = self.db.get(Note, note_id)
        return note if note and note.owner_id == owner_id else None

    def list_for_paper(self, paper_id: uuid.UUID, *, owner_id: str) -> list[Note]:
        return list(
            self.db.scalars(
                select(Note)
                .where(Note.paper_id == paper_id, Note.owner_id == owner_id)
                .order_by(Note.created_at.desc())
            )
        )

    def update(self, note: Note, *, content: str) -> Note:
        note.content = content
        self.db.commit()
        self.db.refresh(note)
        return note

    def delete(self, note: Note) -> None:
        self.db.delete(note)
        self.db.commit()
