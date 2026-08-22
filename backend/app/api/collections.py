import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.repositories.collection_repository import CollectionRepository
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import CollectionCreate, CollectionOut, PaperOut
from app.services.collection_service import CollectionService

router = APIRouter(prefix="/collections", tags=["collections"])

def get_collection_service(db: Session = Depends(get_db)) -> CollectionService:
    return CollectionService(CollectionRepository(db), PaperRepository(db))

@router.post("", response_model=CollectionOut, status_code=201)
def create_collection(
    data: CollectionCreate,
    user_id: str = Depends(get_current_user_id),
    service: CollectionService = Depends(get_collection_service),
) -> CollectionOut:
    return service.create(owner_id=user_id, name=data.name)

@router.get("", response_model=list[CollectionOut])
def list_collections(
    user_id: str = Depends(get_current_user_id),
    service: CollectionService = Depends(get_collection_service),
) -> list[CollectionOut]:
    return service.list_collections(owner_id=user_id)

@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: CollectionService = Depends(get_collection_service),
) -> None:
    service.delete(collection_id, owner_id=user_id)

@router.get("/{collection_id}/papers", response_model=list[PaperOut])
def list_collection_papers(
    collection_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: CollectionService = Depends(get_collection_service),
) -> list[PaperOut]:
    return service.list_papers(collection_id, owner_id=user_id)

@router.post("/{collection_id}/papers/{paper_id}", response_model=CollectionOut)
def add_paper_to_collection(
    collection_id: uuid.UUID,
    paper_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: CollectionService = Depends(get_collection_service),
) -> CollectionOut:
    return service.add_paper(collection_id, paper_id, owner_id=user_id)

@router.delete("/{collection_id}/papers/{paper_id}", response_model=CollectionOut)
def remove_paper_from_collection(
    collection_id: uuid.UUID,
    paper_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: CollectionService = Depends(get_collection_service),
) -> CollectionOut:
    return service.remove_paper(collection_id, paper_id, owner_id=user_id)
