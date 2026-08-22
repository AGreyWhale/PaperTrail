import json
import uuid

from fastapi import HTTPException, status

from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import PaperCreate, PaperOut
from app.storage.base import FileStorage

_PDF_MAGIC_BYTES = b"%PDF-"

class PaperService:
    # Routers call this so validation and future rules live here

    def __init__(self, repository: PaperRepository, storage: FileStorage | None = None):
        self.repository = repository
        self.storage = storage
    
    def add_paper(self, data: PaperCreate, *, owner_id: str) -> PaperOut:
        if not data.title.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Title cannot be empty")
        
        paper = self.repository.create(
            owner_id=owner_id,
            title=data.title.strip(),
            authors=", ".join(a.strip() for a in data.authors if a.strip()),
            venue =data.venue,
            year=data.year,
        )
        return PaperOut.from_model(paper)
    
    def get_paper(self, paper_id: uuid.UUID, *, owner_id: str) -> PaperOut:
        paper = self.repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found")
        return PaperOut.from_model(paper)

    def list_papers(self, *, owner_id: str, tag_id: uuid.UUID | None = None) -> list[PaperOut]:
        return [
            PaperOut.from_model(p)
            for p in self.repository.list_for_owner(owner_id, tag_id=tag_id)
        ]

    def attach_file(
        self,
        paper_id: uuid.UUID,
        *,
        owner_id: str,
        filename: str,
        content: bytes,
        max_size_bytes: int,
    ) -> PaperOut:
        paper = self.repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")
        
        if not content.startswith(_PDF_MAGIC_BYTES):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "File is not a valid PDF")

        if len(content) > max_size_bytes:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"File exceeds the {max_size_bytes // (1024 * 1024)} MB limit")

        #Prevents accumlation of orphans
        storage_key = f"papers/{paper.id}/original.pdf"
        assert self.storage is not None, "attach_file requires a storage backend"
        self.storage.save(key=storage_key, content=content)

        paper = self.repository.attach_file(
            paper,
            storage_key=storage_key,
            original_name=filename,
            size_bytes=len(content),
        )
        return PaperOut.from_model(paper)

    def get_file_content(self, paper_id: uuid.UUID, *, owner_id: str) -> bytes:
        paper = self.repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")
        if paper.file_storage_key is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "This paper has no attached file")

        assert self.storage is not None, "get_file_content requires a storage backend"
        return self.storage.read(key=paper.file_storage_key)

    def record_opened(self, paper_id: uuid.UUID, *, owner_id: str, page: int | None) -> PaperOut:
        paper = self.repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")
        return PaperOut.from_model(self.repository.record_opened(paper, page=page))

    def list_continue_reading(self, *, owner_id: str, limit: int = 4) -> list[PaperOut]:
        return [
            PaperOut.from_model(p)
            for p in self.repository.list_recently_opened(owner_id, limit=limit)
        ]

    def suggested_questions(
        self, paper_id: uuid.UUID, *, owner_id: str, generate
    ) -> list[str]:
        #Cached on the paper, so the model runs once per paper rather than on
        #every home-page load. `generate` is injected to keep the LLM out of here
        paper = self.repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")

        if paper.suggested_questions:
            return json.loads(paper.suggested_questions)

        questions = generate(paper)
        if questions:
            self.repository.set_suggested_questions(paper, json.dumps(questions))
        return questions

    def toggle_favorite(self, paper_id: uuid.UUID, *, owner_id: str) -> PaperOut:
        paper = self.repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")
        return PaperOut.from_model(self.repository.set_favorite(paper, not paper.is_favorite))

    def delete_paper(self, paper_id: uuid.UUID, *, owner_id: str, vector_store=None) -> None:
        #The row cascades to chunks/notes/links, but the stored PDF and the
        #embedded vectors live outside Postgres and have to be cleared here or
        #they outlive the paper
        paper = self.repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")

        storage_key = paper.file_storage_key
        self.repository.delete(paper)

        if storage_key and self.storage is not None:
            self.storage.delete(key=storage_key)
        if vector_store is not None:
            vector_store.delete_for_paper(paper_id)
