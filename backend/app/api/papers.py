import json
import uuid
from pathlib import Path
from typing import Callable

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.core.config import get_settings
from app.core.database import get_db
from app.integrations.crossref.client import CrossRefClient
from app.integrations.embeddings.local_client import EmbeddingsClient
from app.integrations.llm.client import LLMClient, LLMUnavailableError
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.note_repository import NoteRepository
from app.repositories.paper_repository import PaperRepository
from app.repositories.tag_repository import TagRepository
from app.schemas.paper import (
    AskAnswerOut,
    AskRequest,
    ChunkOut,
    NoteCreate,
    NoteOut,
    PaperCreate,
    MultiPaperRequest,
    PaperOut,
    SimilarChunkOut,
    TagCreate,
)
from app.services.doi_lookup_service import DoiLookupService
from app.services.embedding_service import EmbeddingService, PreparationService
from app.services.paper_processing_service import PaperProcessingService
from app.services.bibtex_service import BibtexService
from app.services.note_service import NoteService
from app.services.paper_service import PaperService
from app.services.tag_service import TagService
from app.services.rag_service import RagService
from app.services.search_service import SearchService
from app.storage.base import FileStorage
from app.storage.local import LocalFileStorage
from app.storage.supabase_storage import SupabaseFileStorage

router = APIRouter(prefix="/papers", tags=["papers"])

_QUESTIONS_PROMPT = """You are helping a researcher start reading a paper.
From the excerpt below, write exactly three short questions the paper itself \
can answer. One per line, no numbering, no preamble. Keep each under 12 words."""

def get_file_storage() -> FileStorage:
    settings = get_settings()
    if settings.storage_backend == "supabase":
        return SupabaseFileStorage(
            url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
            bucket=settings.supabase_storage_bucket,
        )
    return LocalFileStorage(root=Path(settings.local_storage_root))


def get_paper_service(db: Session = Depends(get_db), storage: FileStorage = Depends(get_file_storage)) -> PaperService:
    return PaperService(PaperRepository(db), storage)

def get_paper_processing_service(
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
) -> PaperProcessingService:
    return PaperProcessingService(PaperRepository(db), ChunkRepository(db), storage)

def get_tag_service(db: Session = Depends(get_db)) -> TagService:
    return TagService(TagRepository(db), PaperRepository(db))

def get_bibtex_service(db: Session = Depends(get_db)) -> BibtexService:
    return BibtexService(PaperRepository(db))

def get_note_service(db: Session = Depends(get_db)) -> NoteService:
    return NoteService(NoteRepository(db), PaperRepository(db))

def get_doi_lookup_service() -> DoiLookupService:
    settings = get_settings()
    return DoiLookupService(CrossRefClient(contact_email=settings.crossref_contact_email))

def get_embedding_enqueue_fn(
    background_tasks: BackgroundTasks,
) -> Callable[[str, str], None]:
    # Its own dependency so tests can override just the enqueue step and never
    # need a reachable Redis broker. BackgroundTasks is injectable into a
    # dependency the same way it is into an endpoint, so the fallback path gets
    # it here rather than through a global.
    settings = get_settings()

    if settings.embedding_backend == "celery":
        def _enqueue(paper_id: str, owner_id: str) -> None:
            from app.workers.tasks import embed_paper_task

            embed_paper_task.delay(paper_id, owner_id)

        return _enqueue

    def _enqueue_in_process(paper_id: str, owner_id: str) -> None:
        from app.workers.tasks import embed_paper_now

        # Runs after the response is sent, so the endpoint still returns
        # "queued" immediately and the client polls exactly as before.
        background_tasks.add_task(embed_paper_now, paper_id, owner_id)

    return _enqueue_in_process

def get_prepare_enqueue_fn(
    background_tasks: BackgroundTasks,
) -> Callable[[str, str], None]:
    #Same backend switch as embedding, pointed at the combined pipeline
    settings = get_settings()

    if settings.embedding_backend == "celery":
        def _enqueue(paper_id: str, owner_id: str) -> None:
            from app.workers.tasks import prepare_paper_task

            prepare_paper_task.delay(paper_id, owner_id)

        return _enqueue

    def _enqueue_in_process(paper_id: str, owner_id: str) -> None:
        from app.workers.tasks import prepare_paper_now

        background_tasks.add_task(prepare_paper_now, paper_id, owner_id)

    return _enqueue_in_process

def get_preparation_service(
    db: Session = Depends(get_db),
    enqueue_fn: Callable[[str, str], None] = Depends(get_prepare_enqueue_fn),
) -> PreparationService:
    return PreparationService(PaperRepository(db), enqueue_fn)

def get_embedding_service(
    db: Session = Depends(get_db),
    enqueue_fn: Callable[[str, str], None] = Depends(get_embedding_enqueue_fn),
) -> EmbeddingService:
    return EmbeddingService(PaperRepository(db), ChunkRepository(db), enqueue_fn)

def get_chunk_repository(db: Session = Depends(get_db)) -> ChunkRepository:
    #Its own factory so tests can substitute the similarity queries, which are
    #pgvector SQL and don't run on the suite's SQLite database
    return ChunkRepository(db)

def get_embeddings_client() -> EmbeddingsClient:
    settings = get_settings()
    return EmbeddingsClient(model_name=settings.embedding_model)

def get_search_service(
    db: Session = Depends(get_db),
    embeddings_client: EmbeddingsClient = Depends(get_embeddings_client),
    chunk_repository: ChunkRepository = Depends(get_chunk_repository),
) -> SearchService:
    return SearchService(PaperRepository(db), embeddings_client, chunk_repository)

def get_llm_client() -> LLMClient:
    settings = get_settings()
    if not settings.llm_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "LLM API key not configured")
    return LLMClient(
        api_key=settings.llm_api_key, base_url=settings.llm_base_url, model=settings.llm_model
    )

def get_optional_llm_client() -> LLMClient | None:
    #Unlike get_llm_client this returns None instead of 503 — suggested
    #questions are a nicety, and a missing key shouldn't break the home page
    settings = get_settings()
    if not settings.llm_api_key:
        return None
    return LLMClient(
        api_key=settings.llm_api_key, base_url=settings.llm_base_url, model=settings.llm_model
    )

def get_question_generator(
    db: Session = Depends(get_db),
    llm_client: LLMClient | None = Depends(get_optional_llm_client),
) -> Callable[[object], list[str]]:
    def generate(paper) -> list[str]:
        if llm_client is None:
            return []
        chunks = ChunkRepository(db).list_for_paper(paper.id)[:4]
        if not chunks:
            return []
        excerpt = "\n\n".join(c.text for c in chunks)
        try:
            raw = llm_client.complete(
                system=_QUESTIONS_PROMPT, user=f"Title: {paper.title}\n\n{excerpt}"
            )
        except LLMUnavailableError:
            return []
        lines = [line.strip().lstrip("-*0123456789. ").strip() for line in raw.splitlines()]
        return [line for line in lines if line][:3]

    return generate

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


@router.post("/bibtex-export")
def export_bibtex(
    data: MultiPaperRequest,
    user_id: str = Depends(get_current_user_id),
    service: BibtexService = Depends(get_bibtex_service),
) -> Response:
    #Declared above /{paper_id} routes so "bibtex-export" isn't read as a UUID
    return Response(
        content=service.for_papers(data.paper_ids, owner_id=user_id),
        media_type="application/x-bibtex",
        headers={"Content-Disposition": 'attachment; filename="papertrail.bib"'},
    )

@router.get("/continue-reading", response_model=list[PaperOut])
def continue_reading(
    limit: int = Query(4, ge=1, le=20),
    user_id: str = Depends(get_current_user_id),
    service: PaperService = Depends(get_paper_service),
) -> list[PaperOut]:
    #Declared before /{paper_id} so "continue-reading" isn't parsed as a UUID
    return service.list_continue_reading(owner_id=user_id, limit=limit)

@router.post("", response_model=PaperOut,status_code=201)
def add_paper(
    data: PaperCreate, 
    service: PaperService = Depends(get_paper_service),
    user_id: str = Depends(get_current_user_id),
) -> PaperOut :
    return service.add_paper(data, owner_id=user_id)

@router.get("", response_model=list[PaperOut])
def list_papers(
    tag: uuid.UUID | None = Query(None, description="Only papers carrying this tag"),
    user_id: str = Depends(get_current_user_id),
    service: PaperService = Depends(get_paper_service),
) -> list[PaperOut]:
    return service.list_papers(owner_id=user_id, tag_id=tag)

@router.get("/{paper_id}", response_model=PaperOut)
def get_paper(
    paper_id: uuid.UUID, 
    service: PaperService = Depends(get_paper_service),
    user_id: str = Depends(get_current_user_id),
    ) -> PaperOut:
    return service.get_paper(paper_id, owner_id=user_id)


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paper(
    paper_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: PaperService = Depends(get_paper_service),
) -> None:
    # Embeddings live on the chunk rows, which cascade with the paper — there
    # is no separate vector store left to clean up.
    service.delete_paper(paper_id, owner_id=user_id)

@router.patch("/{paper_id}/favorite", response_model=PaperOut)
def toggle_favorite(
    paper_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: PaperService = Depends(get_paper_service),
) -> PaperOut:
    return service.toggle_favorite(paper_id, owner_id=user_id)

@router.post("/{paper_id}/tags", response_model=PaperOut)
def add_tag(
    paper_id: uuid.UUID,
    data: TagCreate,
    user_id: str = Depends(get_current_user_id),
    service: TagService = Depends(get_tag_service),
) -> PaperOut:
    #Creates the tag for this owner if it doesn't exist yet
    return service.add_to_paper(paper_id, owner_id=user_id, name=data.name)

@router.delete("/{paper_id}/tags/{tag_id}", response_model=PaperOut)
def remove_tag(
    paper_id: uuid.UUID,
    tag_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: TagService = Depends(get_tag_service),
) -> PaperOut:
    return service.remove_from_paper(paper_id, tag_id, owner_id=user_id)

@router.post("/{paper_id}/notes", response_model=NoteOut, status_code=201)
def create_note(
    paper_id: uuid.UUID,
    data: NoteCreate,
    user_id: str = Depends(get_current_user_id),
    service: NoteService = Depends(get_note_service),
) -> NoteOut:
    return service.create(
        paper_id,
        owner_id=user_id,
        content=data.content,
        quoted_text=data.quoted_text,
        page_number=data.page_number,
        color=data.color,
    )

@router.get("/{paper_id}/notes", response_model=list[NoteOut])
def list_notes(
    paper_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: NoteService = Depends(get_note_service),
) -> list[NoteOut]:
    return service.list_for_paper(paper_id, owner_id=user_id)

@router.post("/{paper_id}/file", response_model=PaperOut)
async def upload_paper_file(
    paper_id: uuid.UUID,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    service: PaperService = Depends(get_paper_service),
    preparation: PreparationService = Depends(get_preparation_service),
) -> PaperOut:
    settings = get_settings()
    content = await file.read()
    paper = service.attach_file(
        paper_id,
        owner_id=user_id,
        filename=file.filename or "upload.pdf",
        content=content,
        max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )
    #A freshly uploaded PDF is always going to be parsed and embedded, so start
    #it here rather than making the reader press a button to say so
    return preparation.enqueue_preparation(paper_id, owner_id=user_id)

@router.get("/{paper_id}/file")
def get_paper_file(
    paper_id: uuid.UUID,
    service: PaperService = Depends(get_paper_service),
    user_id: str = Depends(get_current_user_id),
) -> Response:
    # Served through the API rather than linked directly: an <iframe src>
    # can't attach the Clerk auth header, so the frontend fetches these
    # bytes itself and renders them from a blob URL.
    content = service.get_file_content(paper_id, owner_id=user_id)
    return Response(content=content, media_type="application/pdf")

@router.post("/{paper_id}/process", response_model=PaperOut)
def process_paper(
    paper_id: uuid.UUID,
    service: PaperProcessingService = Depends(get_paper_processing_service),
    user_id: str = Depends(get_current_user_id),
) -> PaperOut:
    return service.process_paper(paper_id, owner_id=user_id)

@router.post("/{paper_id}/opened", response_model=PaperOut)
def record_paper_opened(
    paper_id: uuid.UUID,
    page: int | None = Query(None, ge=1),
    user_id: str = Depends(get_current_user_id),
    service: PaperService = Depends(get_paper_service),
) -> PaperOut:
    #Called when the reading view opens and as the reader moves through pages
    return service.record_opened(paper_id, owner_id=user_id, page=page)

@router.get("/{paper_id}/suggested-questions", response_model=list[str])
def suggested_questions(
    paper_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: PaperService = Depends(get_paper_service),
    generate: Callable[[object], list[str]] = Depends(get_question_generator),
) -> list[str]:
    return service.suggested_questions(paper_id, owner_id=user_id, generate=generate)

@router.get("/{paper_id}/bibtex")
def paper_bibtex(
    paper_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: BibtexService = Depends(get_bibtex_service),
) -> Response:
    return Response(
        content=service.for_paper(paper_id, owner_id=user_id), media_type="application/x-bibtex"
    )

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
# model or opening a database/LLM connection.

@router.post("/{paper_id}/prepare", response_model=PaperOut)
def prepare_paper(
    paper_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    service: PreparationService = Depends(get_preparation_service),
) -> PaperOut:
    #One step for the reader: parse, chunk and embed. /process and /embed are
    #still there for running either half on its own
    return service.enqueue_preparation(paper_id, owner_id=user_id)

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

@router.post("/{paper_id}/ask/stream")
def ask_paper_question_stream(
    paper_id: uuid.UUID,
    data: AskRequest,
    user_id: str = Depends(get_current_user_id),
    service: RagService = Depends(get_rag_service),
) -> StreamingResponse:
    # NDJSON rather than SSE: we read this with fetch + a stream reader (an
    # EventSource can't send the Clerk auth header), and one JSON object per
    # line is less to get wrong than SSE's framing rules.
    # Retrieval runs here, outside the generator, so a 404/422 is still a real
    # status code instead of an error buried in a 200 body.
    chunks = service.retrieve_context(
        paper_id, owner_id=user_id, question=data.question, top_k=data.top_k
    )

    def emit():
        citations = [
            {"chunk_id": str(c["chunk_id"]), "page_number": c["page_number"], "text": c["text"]}
            for c in chunks
        ]
        yield json.dumps({"type": "citations", "citations": citations}) + "\n"
        try:
            for token in service.stream_answer(data.question, chunks):
                yield json.dumps({"type": "token", "text": token}) + "\n"
        except LLMUnavailableError as exc:
            yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"
            return
        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(emit(), media_type="application/x-ndjson")


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