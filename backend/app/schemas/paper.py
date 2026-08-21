import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

class PaperCreate(BaseModel):
    #When adding a paper
    title: str
    authors: list[str]
    venue: str | None = None
    year: int | None = None

class PaperOut(BaseModel):
    #What API returns
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    authors: list[str]
    venue: str | None
    year: int | None
    created_at: datetime
    has_file: bool
    file_original_name: str | None
    file_size_bytes: int | None
    processing_status: str
    embedding_status: str
    last_opened_at: datetime | None
    last_page: int | None

    @classmethod
    def from_model(cls, paper) -> "PaperOut":
        return cls(
            id=paper.id,
            title=paper.title,
            authors=[a.strip() for a in paper.authors.split(",") if a.strip()],
            venue=paper.venue,
            year=paper.year,
            created_at=paper.created_at,
            has_file=paper.file_storage_key is not None,
            file_original_name=paper.file_original_name,
            file_size_bytes=paper.file_size_bytes,
            processing_status=paper.processing_status,
            embedding_status=paper.embedding_status,
            last_opened_at=paper.last_opened_at,
            last_page=paper.last_page,
        )

class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    chunk_index: int
    page_number: int
    text: str
    token_count: int

class SimilarChunkOut(BaseModel):
    #A chunk matched by semantic search. score is 1 - cosine distance, so higher is better
    chunk_id: uuid.UUID
    text: str
    page_number: int
    score: float

class AskRequest(BaseModel):
    question: str
    top_k: int = 5

class CitationOut(BaseModel):
    #One chunk the answer was actually grounded in
    chunk_id: uuid.UUID
    page_number: int
    text: str

class AskAnswerOut(BaseModel):
    answer: str
    citations: list[CitationOut]

class SearchHitOut(BaseModel):
    #One paper that matched, with its strongest excerpt. The excerpt IS the
    #"why it matched" — no generated explanation needed
    paper_id: uuid.UUID
    title: str
    authors: list[str]
    venue: str | None
    year: int | None
    excerpt: str
    page_number: int
    score: float
    match_count: int
