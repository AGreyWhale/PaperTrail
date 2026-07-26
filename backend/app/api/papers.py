import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.core.config import get_settings
from app.core.database import get_db
from app.integrations.crossref.client import CrossRefClient
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import PaperCreate, PaperOut
from app.services.doi_lookup_service import DoiLookupService
from app.services.paper_service import PaperService
from app.storage.base import FileStorage
from app.storage.local import LocalFileStorage

router = APIRouter(prefix="/papers", tags=["papers"])

def get_file_storage() -> FileStorage:
    settings = get_settings()
    return LocalFileStorage(root=Path(settings.local_storage_root))


def get_paper_service(db: Session = Depends(get_db), storage: FileStorage = Depends(get_file_storage)) -> PaperService:
    return PaperService(PaperRepository(db), storage)

def get_doi_lookup_service() -> DoiLookupService:
    settings = get_settings()
    return DoiLookupService(CrossRefClient(contact_email=settings.crossref_contact_email))

@router.get("/lookup", response_model=PaperCreate)
async def lookup_by_doi(
    doi: str = Query(..., description="A DOI, e.g. 10.1038/nphys1170, or a doi.org URL"),
    service: DoiLookupService = Depends(get_doi_lookup_service),
    _user_id: str = Depends(get_current_user_id),
) -> PaperCreate:
    return await service.lookup(doi)


@router.post("", response_model=PaperOut,status_code=201)
def add_paper(
    data: PaperCreate, 
    service: PaperService = Depends(get_paper_service),
    user_id: str = Depends(get_current_user_id),
) -> PaperOut :
    return service.add_paper(data, owner_id=user_id)

@router.get("", response_model=list[PaperOut])
def list_papers(
    service: PaperService = Depends(get_paper_service),
    user_id: str = Depends(get_current_user_id),
    ) -> list[PaperOut]:
    return service.list_papers(owner_id=user_id)

@router.get("/{paper_id}", response_model=PaperOut)
def get_paper(
    paper_id: uuid.UUID, 
    service: PaperService = Depends(get_paper_service),
    user_id: str = Depends(get_current_user_id),
    ) -> PaperOut:
    return service.get_paper(paper_id, owner_id=user_id)


@router.post("/{paper_id}/file", response_model=PaperOut)
async def upload_paper_file(
    paper_id: uuid.UUID,
    file: UploadFile = File(...),
    service: PaperService = Depends(get_paper_service),
    user_id: str = Depends(get_current_user_id),
) -> PaperOut:
    settings = get_settings()
    content = await file.read()
    return service.attach_file(
        paper_id,
        owner_id=user_id,
        filename=file.filename or "upload.pdf",
        content=content,
        max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )
