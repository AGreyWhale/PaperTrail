import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str

class TagCreate(BaseModel):
    name: str

class CollectionRef(BaseModel):
    #Just enough to show membership on a paper
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str

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
    embedding_error: str | None
    is_favorite: bool
    tags: list["TagOut"]
    collections: list["CollectionRef"]
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
            embedding_error=paper.embedding_error,
            is_favorite=paper.is_favorite,
            tags=[TagOut.model_validate(t) for t in paper.tags],
            collections=[CollectionRef.model_validate(c) for c in paper.collections],
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

class CollectionOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    paper_count: int

class CollectionCreate(BaseModel):
    name: str

class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    paper_id: uuid.UUID
    content: str
    quoted_text: str | None
    page_number: int | None
    color: str | None
    created_at: datetime
    updated_at: datetime

class RecentNoteOut(NoteOut):
    #A note plus the paper it belongs to, for the home page's panel
    paper_title: str

class NoteCreate(BaseModel):
    content: str = ""
    quoted_text: str | None = None
    page_number: int | None = None
    color: str | None = None

class NoteUpdate(BaseModel):
    content: str

class MultiPaperRequest(BaseModel):
    #Shared by compare and literature review — both start from "pick 2+ papers"
    paper_ids: list[uuid.UUID]

class ComparisonRowOut(BaseModel):
    #One paper's column in the comparison table
    paper_id: uuid.UUID
    title: str
    datasets: str
    architecture: str
    evaluation_metrics: str
    strengths: str
    weaknesses: str
    future_work: str

class ComparisonOut(BaseModel):
    papers: list[ComparisonRowOut]

class ReviewSourceOut(BaseModel):
    paper_id: uuid.UUID
    title: str
    citation: str

class ThemeCellOut(BaseModel):
    #What one paper says about one theme
    paper_id: uuid.UUID
    position: str

class ThemeOut(BaseModel):
    theme: str
    cells: list[ThemeCellOut]

class LiteratureReviewOut(BaseModel):
    #themes render as a themes-by-papers table, markdown as the narrative below
    themes: list[ThemeOut]
    markdown: str
    sources: list[ReviewSourceOut]
