import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import PaperCreate, PaperOut
from app.services.paper_service import PaperService

router = APIRouter(prefix="/papers", tags=["papers"])

def get_paper_service(db: Session = Depends(get_db)) -> PaperSErvice:
    return PaperService(PaperRepository(db))

@router.post("", response_model=PaperOut,status_code=201)
def add_paper(data:PaperCreate, service: PaperService = Depends(get_paper_service)) -> PaperOut :
    return service.add_paper(data)

@router.get("", response_model=list[PaperOut])
def list_papers(service: PaperService = Depends(get_paper_service)) -> list[PaperOut]:
    return service.list_papers()

@router.get("/{paper_id}", response_model=PaperOut)
def get_paper(paper_id: uuid.UUID, service: PaperService = Depends(get_paper_service)) -> PaperOut:
    return service.get_paper(paper_id)