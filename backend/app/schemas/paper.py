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

    @classmethod
    def from_model(cls, paper) -> "PaperOut":
        return cls(
            id=paper.id,
            title=paper.title,
            authors=[a.strip() for a in paper.authors.split(",") if a.strip()],
            venue=paper.venue,
            year=paper.year,
            created_at=paper.created_at,
        )
