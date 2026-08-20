import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
