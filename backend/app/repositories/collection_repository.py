import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.collection import Collection, collection_papers
from app.models.paper import Paper

class CollectionRepository:
    #Owns all database access for Collection

    def __init__(self, db: Session):
        self.db = db

    def create(self, *, owner_id: str, name: str) -> Collection:
        collection = Collection(owner_id=owner_id, name=name)
        self.db.add(collection)
        self.db.commit()
        self.db.refresh(collection)
        return collection

    def get(self, collection_id: uuid.UUID, *, owner_id: str) -> Collection | None:
        collection = self.db.get(Collection, collection_id)
        return collection if collection and collection.owner_id == owner_id else None

    def list_with_counts(self, owner_id: str) -> list[tuple[Collection, int]]:
        #One grouped query rather than len(c.papers) per row
        rows = self.db.execute(
            select(Collection, func.count(collection_papers.c.paper_id))
            .outerjoin(collection_papers, Collection.id == collection_papers.c.collection_id)
            .where(Collection.owner_id == owner_id)
            .group_by(Collection.id)
            .order_by(Collection.created_at.desc())
        ).all()
        return [(row[0], row[1]) for row in rows]

    def delete(self, collection: Collection) -> None:
        self.db.delete(collection)
        self.db.commit()

    def add_paper(self, collection: Collection, paper: Paper) -> Collection:
        if paper not in collection.papers:
            collection.papers.append(paper)
            self.db.commit()
            self.db.refresh(collection)
        return collection

    def remove_paper(self, collection: Collection, paper: Paper) -> Collection:
        if paper in collection.papers:
            collection.papers.remove(paper)
            self.db.commit()
            self.db.refresh(collection)
        return collection

    def list_papers(self, collection: Collection) -> list[Paper]:
        return sorted(collection.papers, key=lambda p: p.created_at, reverse=True)
