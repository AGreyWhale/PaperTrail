import uuid

from fastapi import HTTPException, status

from app.models.collection import Collection
from app.repositories.collection_repository import CollectionRepository
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import CollectionOut, PaperOut

class CollectionService:
    #Collection rules live here, routers just call in

    def __init__(
        self, collection_repository: CollectionRepository, paper_repository: PaperRepository
    ):
        self.collection_repository = collection_repository
        self.paper_repository = paper_repository

    def create(self, *, owner_id: str, name: str) -> CollectionOut:
        cleaned = name.strip()
        if not cleaned:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Collection name cannot be empty"
            )
        collection = self.collection_repository.create(owner_id=owner_id, name=cleaned)
        return self._to_out(collection, 0)

    def list_collections(self, *, owner_id: str) -> list[CollectionOut]:
        return [
            self._to_out(collection, count)
            for collection, count in self.collection_repository.list_with_counts(owner_id)
        ]

    def delete(self, collection_id: uuid.UUID, *, owner_id: str) -> None:
        self.collection_repository.delete(self._require(collection_id, owner_id=owner_id))

    def add_paper(
        self, collection_id: uuid.UUID, paper_id: uuid.UUID, *, owner_id: str
    ) -> CollectionOut:
        collection = self._require(collection_id, owner_id=owner_id)
        paper = self.paper_repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")

        collection = self.collection_repository.add_paper(collection, paper)
        return self._to_out(collection, len(collection.papers))

    def remove_paper(
        self, collection_id: uuid.UUID, paper_id: uuid.UUID, *, owner_id: str
    ) -> CollectionOut:
        collection = self._require(collection_id, owner_id=owner_id)
        paper = self.paper_repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")

        collection = self.collection_repository.remove_paper(collection, paper)
        return self._to_out(collection, len(collection.papers))

    def list_papers(self, collection_id: uuid.UUID, *, owner_id: str) -> list[PaperOut]:
        collection = self._require(collection_id, owner_id=owner_id)
        return [PaperOut.from_model(p) for p in self.collection_repository.list_papers(collection)]

    def _require(self, collection_id: uuid.UUID, *, owner_id: str) -> Collection:
        collection = self.collection_repository.get(collection_id, owner_id=owner_id)
        if collection is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Collection not found")
        return collection

    @staticmethod
    def _to_out(collection: Collection, paper_count: int) -> CollectionOut:
        return CollectionOut(
            id=collection.id,
            name=collection.name,
            created_at=collection.created_at,
            paper_count=paper_count,
        )
