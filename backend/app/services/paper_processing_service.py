import uuid

from fastapi import HTTPException, status

from app.chunking.chunker import chunk_pages
from app.parsing.pdf_parser import extract_pages
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import ChunkOut, PaperOut
from app.storage.base import FileStorage

class PaperProcessingService:
    #Turns PDF into retrievable chunks. 

    def __init__(
        self,
        paper_repository: PaperRepository,
        chunk_repository: ChunkRepository,
        storage: FileStorage,
    ):
        self.paper_repository = paper_repository
        self.chunk_repository = chunk_repository
        self.storage = storage
    
    def process_paper(self, paper_id: uuid.UUID, *, owner_id: str) -> PaperOut:
        paper = self.paper_repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found")
        if paper.file_storage_key is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "This paper has no attached file to process, upload one first",
                )
        self.paper_repository.set_processing_status(paper, "processing")

        try:
            content = self.storage.read(key=paper.file_storage_key)
            pages = extract_pages(content)
            chunks = chunk_pages(pages)
            self.chunk_repository.replace_all_for_paper(paper.id, chunks)
        except Exception as exc:
            self.paper_repository.set_processing_status(paper, "failed")
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, f"Processing failed {exc}"
            ) from exc
        
        paper = self.paper_repository.set_processing_status(paper, "processed")
        return PaperOut.from_model(paper)
    
    def list_chunks(self, paper_id: uuid.UUID, *, owner_id: str) -> list[ChunkOut]:
        paper = self.paper_repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found")
        return [ChunkOut.model_validate(c) for c in self.chunk_repository.list_for_paper(paper_id)]