import uuid
from pathlib import Path
from typing import Callable

import chromadb
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.core.config import get_settings
from app.core.database import get_db
from app.integrations.crossref.client import CrossRefClient
from app.integrations.embeddings.local_client import EmbeddingsClient
from app.integrations.llm.client import LLMClient
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import (
    AskAnswerOut,
    AskRequest,
    ChunkOut,
    PaperCreate,
    PaperOut,
    SimilarChunkOut,
)
from app.services.doi_lookup_service import DoiLookupService
from app.services.embedding_service import EmbeddingService
from app.services.paper_processing_service import PaperProcessingService
from app.services.paper_service import PaperService
from app.services.rag_service import RagService
from app.services.search_service import SearchService
from app.storage.base import FileStorage
from app.storage.local import LocalFileStorage
from app.vectorstore.client import VectorStore

router = APIRouter(prefix="/papers", tags=["papers"])

def get_file_storage() -> FileStorage:
    settings = get_settings()
    return LocalFileStorage(root=Path(settings.local_storage_root))


def get_paper_service(db: Session = Depends(get_db), storage: FileStorage = Depends(get_file_storage)) -> PaperService:
    return PaperService(PaperRepository(db), storage)

def get_paper_processing_service(
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
) -> PaperProcessingService:
    return PaperProcessingService(PaperRepository(db), ChunkRepository(db), storage)

def get_doi_lookup_service() -> DoiLookupService:
    settings = get_settings()
    return DoiLookupService(CrossRefClient(contact_email=settings.crossref_contact_email))

def get_embedding_enqueue_fn() -> Callable[[str, str], None]:
    # Its own dependency so tests can override just the enqueue step and
    # never need a reachable Redis broker.
    def _enqueue(paper_id: str, owner_id: str) -> None:
        from app.workers.tasks import embed_paper_task

        embed_paper_task.delay(paper_id, owner_id)

    return _enqueue

def get_embedding_service(
    db: Session = Depends(get_db),
    enqueue_fn: Callable[[str, str], None] = Depends(get_embedding_enqueue_fn),
) -> EmbeddingService:
    return EmbeddingService(PaperRepository(db), ChunkRepository(db), enqueue_fn)

def get_embeddings_client() -> EmbeddingsClient:
    settings = get_settings()
    return EmbeddingsClient(model_name=settings.embedding_model)

def get_vector_store() -> VectorStore:
    settings = get_settings()
    return VectorStore(chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port))

def get_search_service(
    db: Session = Depends(get_db),
    embeddings_client: EmbeddingsClient = Depends(get_embeddings_client),
    vector_store: VectorStore = Depends(get_vector_store),
) -> SearchService:
    return SearchService(PaperRepository(db), embeddings_client, vector_store)

def get_llm_client() -> LLMClient:
    settings = get_settings()
    if not settings.llm_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "LLM API key not configured")
    return LLMClient(
        api_key=settings.llm_api_key, base_url=settings.llm_base_url, model=settings.llm_model
    )

def get_rag_service(
    search_service: SearchService = Depends(get_search_service),
    llm_client: LLMClient = Depends(get_llm_client),
) -> RagService:
    return RagService(search_service, llm_client)

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

@router.post("/{paper_id}/process", response_model=PaperOut)
def process_paper(
    paper_id: uuid.UUID,
    service: PaperProcessingService = Depends(get_paper_processing_service),
    user_id: str = Depends(get_current_user_id),
) -> PaperOut:
    return service.process_paper(paper_id, owner_id=user_id)

@router.get("/{paper_id}/chunks", response_model=list[ChunkOut])
def list_chunks(
    paper_id: uuid.UUID,
    service: PaperProcessingService = Depends(get_paper_processing_service),
    user_id: str = Depends(get_current_user_id),
) -> list[ChunkOut]:
    return service.list_chunks(paper_id, owner_id=user_id)

# user_id comes before service on these three: FastAPI resolves
# dependencies in signature order, so putting auth first means an
# unauthenticated request 401s without first loading the embeddings
# model or opening a Chroma/LLM connection.

@router.post("/{paper_id}/embed", response_model=PaperOut)
def embed_paper(
    paper_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: EmbeddingService = Depends(get_embedding_service),
) -> PaperOut:
    # Returns straight away with embedding_status="queued"; poll
    # GET /papers/{id} to watch it reach "embedded" or "failed".
    return service.enqueue_embedding(paper_id, owner_id=user_id)

@router.get("/{paper_id}/similar", response_model=list[SimilarChunkOut])
def search_similar_chunks(
    paper_id: uuid.UUID,
    query: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
    user_id: str = Depends(get_current_user_id),
    service: SearchService = Depends(get_search_service),
) -> list[SimilarChunkOut]:
    return service.search_within_paper(paper_id, owner_id=user_id, query=query, top_k=top_k)

@router.post("/{paper_id}/ask", response_model=AskAnswerOut)
def ask_paper_question(
    paper_id: uuid.UUID,
    data: AskRequest,
    user_id: str = Depends(get_current_user_id),
    service: RagService = Depends(get_rag_service),
) -> AskAnswerOut:
    result = service.answer_question(
        paper_id, owner_id=user_id, question=data.question, top_k=data.top_k
    )
    return AskAnswerOut(**result)