import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user_id
from app.core.database import Base, get_db
from app.main import app

TEST_USER_ID = "user_test123"


@pytest.fixture()
def client():
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
    yield TestClient(app)
    app.dependency_overrides.clear()
