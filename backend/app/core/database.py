from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    
    pass

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a DB session and guarantees it's
    closed after the request, even if the handler raises.
    Routers depend on this, never on `SessionLocal` directly — that
    keeps DB session lifecycle out of business logic.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Imported at the bottom (after Base is defined) so every model
# registers itself on Base.metadata as soon as this module loads —
# app startup and tests both get a complete schema for free.
from app import models  # noqa: E402, F401