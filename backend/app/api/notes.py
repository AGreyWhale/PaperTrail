import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.repositories.note_repository import NoteRepository
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import NoteOut, NoteUpdate, RecentNoteOut
from app.services.note_service import NoteService

router = APIRouter(prefix="/notes", tags=["notes"])

def get_note_service(db: Session = Depends(get_db)) -> NoteService:
    return NoteService(NoteRepository(db), PaperRepository(db))

@router.get("/recent", response_model=list[RecentNoteOut])
def recent_notes(
    limit: int = Query(5, ge=1, le=20),
    user_id: str = Depends(get_current_user_id),
    service: NoteService = Depends(get_note_service),
) -> list[RecentNoteOut]:
    #Above /{note_id} so "recent" isn't parsed as a UUID
    return service.list_recent(owner_id=user_id, limit=limit)

@router.patch("/{note_id}", response_model=NoteOut)
def update_note(
    note_id: uuid.UUID,
    data: NoteUpdate,
    user_id: str = Depends(get_current_user_id),
    service: NoteService = Depends(get_note_service),
) -> NoteOut:
    return service.update(note_id, owner_id=user_id, content=data.content)

@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: NoteService = Depends(get_note_service),
) -> None:
    service.delete(note_id, owner_id=user_id)
