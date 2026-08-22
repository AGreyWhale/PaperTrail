import uuid

from fastapi import HTTPException, status

from app.repositories.paper_repository import PaperRepository
from app.repositories.tag_repository import TagRepository
from app.schemas.paper import PaperOut, TagOut

_MAX_TAG_LENGTH = 60

class TagService:
    #Tagging rules live here, routers just call in

    def __init__(self, tag_repository: TagRepository, paper_repository: PaperRepository):
        self.tag_repository = tag_repository
        self.paper_repository = paper_repository

    def list_tags(self, *, owner_id: str) -> list[TagOut]:
        return [TagOut.model_validate(t) for t in self.tag_repository.list_for_owner(owner_id)]

    def add_to_paper(self, paper_id: uuid.UUID, *, owner_id: str, name: str) -> PaperOut:
        cleaned = name.strip().lower()
        if not cleaned:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Tag name cannot be empty")
        if len(cleaned) > _MAX_TAG_LENGTH:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Tag name cannot exceed {_MAX_TAG_LENGTH} characters",
            )

        paper = self.paper_repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")

        tag = self.tag_repository.get_or_create(owner_id=owner_id, name=cleaned)
        return PaperOut.from_model(self.tag_repository.attach(paper, tag))

    def remove_from_paper(
        self, paper_id: uuid.UUID, tag_id: uuid.UUID, *, owner_id: str
    ) -> PaperOut:
        paper = self.paper_repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")
        tag = self.tag_repository.get(tag_id, owner_id=owner_id)
        if tag is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")

        return PaperOut.from_model(self.tag_repository.detach(paper, tag))
