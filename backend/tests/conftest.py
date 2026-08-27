import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.papers import (
    get_embedding_enqueue_fn,
    get_file_storage,
    get_prepare_enqueue_fn,
)
from app.core.auth import get_current_user_id
from app.core.database import Base, get_db
from app.main import app
from app.storage.local import LocalFileStorage


TEST_USER_ID = "user_test123"

@pytest.fixture()
def anyio_backend():
    return "asyncio"

@pytest.fixture()
def client(tmp_path):
    """
    Spins up the FastAPI app against an isolated in-memory SQLite DB,
    so tests never touch a real Postgres instance and each test starts
    from a clean schema.

    StaticPool is required here: by default every new connection to
    sqlite ':memory:' gets its OWN empty database, so without it,
    the session that creates the schema and the session that serves
    a request would silently be talking to two different databases.

    Auth is overridden to a fixed test user by default, since these
    tests shouldn't depend on hitting Clerk's real servers — real
    token verification is covered separately in test_auth.py with a
    mocked Clerk client.

    Enqueueing defaults to a no-op so hitting POST /papers/{id}/embed
    never needs a live Redis broker. Tests that care about what got
    enqueued override it further themselves.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(root=tmp_path)
    app.dependency_overrides[get_embedding_enqueue_fn] = lambda: (lambda paper_id, owner_id: None)
    app.dependency_overrides[get_prepare_enqueue_fn] = lambda: (lambda paper_id, owner_id: None)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def db_session_factory():
    """A bare session plus one processed paper with chunks, for tests that
    exercise the job function directly rather than through the API."""
    from app.models.chunk import Chunk
    from app.models.paper import Paper

    def _make():
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        paper = Paper(
            owner_id="user_1", title="A Paper", authors="A. Author",
            processing_status="processed",
        )
        db.add(paper)
        db.commit()
        db.refresh(paper)
        db.add(Chunk(paper_id=paper.id, chunk_index=0, page_number=1, text="Content.", token_count=10))
        db.commit()
        return db, paper

    return _make
