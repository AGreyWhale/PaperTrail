from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.repositories.paper_repository import PaperRepository
from app.repositories.tag_repository import TagRepository
from app.schemas.paper import TagOut
from app.services.tag_service import TagService

router = APIRouter(prefix="/tags", tags=["tags"])

def get_tag_service(db: Session = Depends(get_db)) -> TagService:
    return TagService(TagRepository(db), PaperRepository(db))

@router.get("", response_model=list[TagOut])
def list_tags(
    user_id: str = Depends(get_current_user_id),
    service: TagService = Depends(get_tag_service),
) -> list[TagOut]:
    #Powers autocomplete and the library's tag filter row
    return service.list_tags(owner_id=user_id)
