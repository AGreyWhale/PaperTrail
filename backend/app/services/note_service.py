import uuid

from fastapi import HTTPException, status

from app.repositories.note_repository import NoteRepository
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import NoteOut

class NoteService:
    #Note rules live here, routers just call in

    def __init__(self, note_repository: NoteRepository, paper_repository: PaperRepository):
        self.note_repository = note_repository
        self.paper_repository = paper_repository

    def create(
        self,
        paper_id: uuid.UUID,
        *,
        owner_id: str,
        content: str,
        quoted_text: str | None,
        page_number: int | None,
        color: str | None = None,
    ) -> NoteOut:
        # A highlight is a note that starts as just a quote, so blank content is
        # allowed as long as something was actually selected.
        if not content.strip() and not (quoted_text or "").strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Note cannot be empty")
        if self.paper_repository.get(paper_id, owner_id=owner_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")

        note = self.note_repository.create(
            paper_id=paper_id,
            owner_id=owner_id,
            content=content.strip(),
            quoted_text=quoted_text,
            page_number=page_number,
            color=color,
        )
        return NoteOut.model_validate(note)

    def list_for_paper(self, paper_id: uuid.UUID, *, owner_id: str) -> list[NoteOut]:
        if self.paper_repository.get(paper_id, owner_id=owner_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")
        return [
            NoteOut.model_validate(n)
            for n in self.note_repository.list_for_paper(paper_id, owner_id=owner_id)
        ]

    def update(self, note_id: uuid.UUID, *, owner_id: str, content: str) -> NoteOut:
        note = self.note_repository.get(note_id, owner_id=owner_id)
        if note is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
        if not content.strip() and not (note.quoted_text or "").strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Note cannot be empty")
        return NoteOut.model_validate(self.note_repository.update(note, content=content.strip()))

    def delete(self, note_id: uuid.UUID, *, owner_id: str) -> None:
        note = self.note_repository.get(note_id, owner_id=owner_id)
        if note is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
        self.note_repository.delete(note)
