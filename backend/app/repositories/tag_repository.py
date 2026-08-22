import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.paper import Paper
from app.models.tag import Tag

class TagRepository:
    #Owns all database access for Tag

    def __init__(self, db: Session):
        self.db = db

    def get(self, tag_id: uuid.UUID, *, owner_id: str) -> Tag | None:
        tag = self.db.get(Tag, tag_id)
        return tag if tag and tag.owner_id == owner_id else None

    def list_for_owner(self, owner_id: str) -> list[Tag]:
        return list(
            self.db.scalars(select(Tag).where(Tag.owner_id == owner_id).order_by(Tag.name))
        )

    def get_or_create(self, *, owner_id: str, name: str) -> Tag:
        #Tag names are unique per owner, so reuse before inserting
        existing = self.db.scalars(
            select(Tag).where(Tag.owner_id == owner_id, Tag.name == name)
        ).first()
        if existing:
            return existing

        tag = Tag(owner_id=owner_id, name=name)
        self.db.add(tag)
        self.db.commit()
        self.db.refresh(tag)
        return tag

    def attach(self, paper: Paper, tag: Tag) -> Paper:
        if tag not in paper.tags:
            paper.tags.append(tag)
            self.db.commit()
            self.db.refresh(paper)
        return paper

    def detach(self, paper: Paper, tag: Tag) -> Paper:
        if tag in paper.tags:
            paper.tags.remove(tag)
            self.db.commit()
            self.db.refresh(paper)
        return paper
