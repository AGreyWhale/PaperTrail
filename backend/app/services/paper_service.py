import uuid

from fastapi import HTTPException, status

from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import PaperCreate, PaperOut

class PaperService:
    # Routers call this so validation and future rules live here

    def __init__(self, repository: PaperRepository):
        self.repository = repository
    
    def add_paper(self, data: PaperCreate) -> PaperOut:
        if not data.title.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Title cannot be empty")
        
        paper = self.repository.create(
            title=data.title.strip(),
            authors=", ".join(a.strip() for a in data.authors if a.strip()),
            venue =data.venue,
            year=data.year,
        )
        return PaperOut.from_model(paper)
    
    def get_paper(self, paper_id: uuid.UUID) -> PaperOut:
        paper = self.repository.get(paper_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found")
        return PaperOut.from_model(paper)

    def list_papers(self) -> list[PaperOut]:
        return [PaperOut.from_model(p) for p in self.repository.list_all()]