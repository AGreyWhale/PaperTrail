import io
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.papers import get_prepare_enqueue_fn
from app.core.auth import get_current_user_id
from app.core.database import Base
from app.main import app
from app.models.chunk import Chunk
from app.models.paper import Paper
from app.storage.local import LocalFileStorage
from app.workers.prepare_job import run_prepare_job
from tests.fakes import FakeEmbeddingsClient
from tests.pdf_helpers import make_test_pdf

_PDF = make_test_pdf(["A sentence of real prose about transformers. " * 20])


def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _paper_with_file(db, storage, *, owner_id="user_1") -> Paper:
    paper = Paper(owner_id=owner_id, title="A Paper", authors="A. Author")
    db.add(paper)
    db.commit()
    db.refresh(paper)
    key = f"papers/{paper.id}/original.pdf"
    storage.save(key=key, content=_PDF)
    paper.file_storage_key = key
    db.commit()
    db.refresh(paper)
    return paper


def _create_paper(client) -> str:
    return client.post(
        "/api/papers", json={"title": "A Paper", "authors": ["Someone"]}
    ).json()["id"]


# --- the combined job ---

def test_prepare_parses_and_embeds_in_one_pass(tmp_path):
    db = _db()
    storage = LocalFileStorage(root=Path(tmp_path))
    paper = _paper_with_file(db, storage)

    run_prepare_job(
        paper.id,
        owner_id="user_1",
        db=db,
        storage=storage,
        embeddings_client=FakeEmbeddingsClient(),
    )

    db.refresh(paper)
    assert paper.processing_status == "processed"
    assert paper.embedding_status == "embedded"
    chunks = db.query(Chunk).filter(Chunk.paper_id == paper.id).all()
    assert len(chunks) > 0
    # Every chunk carries a vector — parsed AND embedded, not just parsed.
    assert all(c.embedding is not None for c in chunks)


def test_a_parse_failure_records_the_reason_and_stops(tmp_path):
    db = _db()
    storage = LocalFileStorage(root=Path(tmp_path))
    paper = _paper_with_file(db, storage)
    storage.save(key=paper.file_storage_key, content=b"not a pdf at all")

    try:
        run_prepare_job(
            paper.id, owner_id="user_1", db=db, storage=storage,
            embeddings_client=FakeEmbeddingsClient(),
        )
    except Exception:
        pass

    db.refresh(paper)
    assert paper.processing_status == "failed"
    # Embedding never ran, and the reason is recorded where the UI reads it.
    assert paper.embedding_status == "failed"
    assert paper.embedding_error


def test_a_pdf_with_no_usable_text_is_a_failure_not_a_ready_paper(tmp_path):
    db = _db()
    storage = LocalFileStorage(root=Path(tmp_path))
    paper = _paper_with_file(db, storage)
    storage.save(key=paper.file_storage_key, content=make_test_pdf([" "]))

    try:
        run_prepare_job(
            paper.id, owner_id="user_1", db=db, storage=storage,
            embeddings_client=FakeEmbeddingsClient(),
        )
    except Exception:
        pass

    db.refresh(paper)
    assert paper.processing_status == "failed"
    assert "no usable text" in paper.embedding_error


def test_prepare_ignores_a_paper_deleted_after_queueing(tmp_path):
    db = _db()
    storage = LocalFileStorage(root=Path(tmp_path))
    paper = _paper_with_file(db, storage)
    paper_id = paper.id
    db.delete(paper)
    db.commit()

    run_prepare_job(
        paper_id, owner_id="user_1", db=db, storage=storage,
        embeddings_client=FakeEmbeddingsClient(),
    )


# --- the endpoint and the auto-trigger ---

def test_uploading_a_pdf_starts_preparation_automatically(client):
    queued = []
    app.dependency_overrides[get_prepare_enqueue_fn] = lambda: (
        lambda paper_id, owner_id: queued.append(paper_id)
    )
    paper_id = _create_paper(client)

    response = client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("p.pdf", io.BytesIO(_PDF), "application/pdf")},
    )

    # No second button press needed.
    assert response.status_code == 200
    assert queued == [paper_id]
    assert response.json()["embedding_status"] == "queued"
    assert response.json()["has_file"] is True


def test_prepare_endpoint_queues_the_combined_pipeline(client):
    queued = []
    app.dependency_overrides[get_prepare_enqueue_fn] = lambda: (
        lambda paper_id, owner_id: queued.append((paper_id, owner_id))
    )
    paper_id = _create_paper(client)
    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("p.pdf", io.BytesIO(_PDF), "application/pdf")},
    )
    queued.clear()

    response = client.post(f"/api/papers/{paper_id}/prepare")

    assert response.status_code == 200
    assert queued == [(paper_id, "user_test123")]


def test_prepare_refuses_a_paper_with_no_pdf(client):
    paper_id = _create_paper(client)

    response = client.post(f"/api/papers/{paper_id}/prepare")

    assert response.status_code == 422
    assert "Attach a PDF" in response.json()["detail"]


def test_prepare_clears_a_previous_failure(client):
    paper_id = _create_paper(client)
    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("p.pdf", io.BytesIO(_PDF), "application/pdf")},
    )
    from app.core.database import get_db
    from app.repositories.paper_repository import PaperRepository
    import uuid as _uuid

    db = next(app.dependency_overrides[get_db]())
    repo = PaperRepository(db)
    paper = repo.get(_uuid.UUID(paper_id), owner_id="user_test123")
    repo.set_embedding_status(paper, "failed", error="RuntimeError: boom")

    body = client.post(f"/api/papers/{paper_id}/prepare").json()

    assert body["embedding_status"] == "queued"
    assert body["embedding_error"] is None


def test_prepare_refuses_another_users_paper(client):
    app.dependency_overrides[get_current_user_id] = lambda: "user_alice"
    paper_id = _create_paper(client)
    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("p.pdf", io.BytesIO(_PDF), "application/pdf")},
    )

    app.dependency_overrides[get_current_user_id] = lambda: "user_bob"
    assert client.post(f"/api/papers/{paper_id}/prepare").status_code == 404
