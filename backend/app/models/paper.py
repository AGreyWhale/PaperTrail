import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, false
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Paper(Base):
    """
    A single research paper in a user's library. Minimal for now.
    """

    __tablename__ = "papers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[str] = mapped_column(Text, nullable=False)  # comma-separated for now
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    file_storage_key: Mapped[str | None] = mapped_column(String(500), nullable = True)
    file_original_name: Mapped[str | None] = mapped_column(String(500), nullable = True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable = True)
    
    processing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="unprocessed"
    )

    # not_embedded -> queued -> embedding -> embedded, or failed.
    # Separate from processing_status because chunking and embedding
    # fail independently and either can be retried on its own.
    embedding_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="not_embedded"
    )

    # server_default so the NOT NULL column can land on a table that already
    # has rows. false() not the string "false" — SQLite has no boolean type and
    # stores that string as truthy, which made every new paper favorited.
    is_favorite: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    # Why the last embedding attempt failed. Nullable and cleared on a
    # successful run, so a failure is debuggable instead of a dead end.
    embedding_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Reading progress, for the home page's Continue Reading section.
    # Both null until the paper is opened for the first time.
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cached LLM-generated starter questions, JSON-encoded. Generated once per
    # paper on first request, since it costs a model call.
    suggested_questions: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    tags = relationship("Tag", secondary="paper_tags", back_populates="papers")
    collections = relationship(
        "Collection", secondary="collection_papers", back_populates="papers"
    )
