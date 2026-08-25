import io

from app.api.papers import get_embedding_enqueue_fn
from app.core.auth import get_current_user_id
from app.main import app
from app.models.paper import Paper
from app.repositories.paper_repository import PaperRepository
from app.workers.embedding_job import run_embedding_job
from tests.fakes import FakeEmbeddingsClient
from tests.pdf_helpers import make_test_pdf


class BrokenEmbeddingsClient:
    def embed_documents(self, texts):
        raise RuntimeError("model weights unavailable")


def _processed_paper(client) -> str:
    paper_id = client.post(
        "/api/papers", json={"title": "A Paper", "authors": ["Someone"]}
    ).json()["id"]
    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("p.pdf", io.BytesIO(make_test_pdf(["Content. " * 40])), "application/pdf")},
    )
    client.post(f"/api/papers/{paper_id}/process")
    return paper_id


def test_a_failed_job_records_why(db_session_factory):
    db, paper = db_session_factory()

    try:
        run_embedding_job(
            paper.id, owner_id="user_1", db=db, embeddings_client=BrokenEmbeddingsClient()
        )
    except RuntimeError:
        pass

    db.refresh(paper)
    assert paper.embedding_status == "failed"
    # The message, not just the status — a bare enum is a dead end.
    assert "model weights unavailable" in paper.embedding_error
    assert "RuntimeError" in paper.embedding_error


def test_a_successful_run_clears_a_previous_error(db_session_factory):
    db, paper = db_session_factory()
    PaperRepository(db).set_embedding_status(paper, "failed", error="an earlier failure")

    run_embedding_job(
        paper.id, owner_id="user_1", db=db, embeddings_client=FakeEmbeddingsClient()
    )

    db.refresh(paper)
    assert paper.embedding_status == "embedded"
    assert paper.embedding_error is None


def test_embedding_error_is_exposed_on_the_api(client):
    paper_id = _processed_paper(client)
    assert client.get(f"/api/papers/{paper_id}").json()["embedding_error"] is None


def test_a_failed_paper_can_be_retried_through_the_same_endpoint(client):
    #Retry reuses the existing embed endpoint end to end rather than a
    #parallel code path — this pins that it accepts a failed paper
    calls = []
    app.dependency_overrides[get_embedding_enqueue_fn] = lambda: (
        lambda paper_id, owner_id: calls.append(paper_id)
    )
    paper_id = _processed_paper(client)

    # First attempt fails somewhere downstream.
    client.post(f"/api/papers/{paper_id}/embed")
    from app.core.database import get_db

    db = next(app.dependency_overrides[get_db]())
    repo = PaperRepository(db)
    paper = repo.get(__import__("uuid").UUID(paper_id), owner_id="user_test123")
    repo.set_embedding_status(paper, "failed", error="RuntimeError: boom")

    assert client.get(f"/api/papers/{paper_id}").json()["embedding_error"] == "RuntimeError: boom"

    # Retrying re-queues it and wipes the stale error.
    retried = client.post(f"/api/papers/{paper_id}/embed")

    assert retried.status_code == 200
    assert retried.json()["embedding_status"] == "queued"
    assert retried.json()["embedding_error"] is None
    assert len(calls) == 2


def test_retry_still_refuses_a_paper_that_was_never_processed(client):
    paper_id = client.post(
        "/api/papers", json={"title": "Unprocessed", "authors": ["Someone"]}
    ).json()["id"]

    assert client.post(f"/api/papers/{paper_id}/embed").status_code == 422


def test_retry_refuses_another_users_paper(client):
    app.dependency_overrides[get_current_user_id] = lambda: "user_alice"
    paper_id = _processed_paper(client)

    app.dependency_overrides[get_current_user_id] = lambda: "user_bob"
    assert client.post(f"/api/papers/{paper_id}/embed").status_code == 404


def test_a_job_that_writes_no_vectors_is_a_failure_not_a_success(db_session_factory):
    #The silent-failure mode: a paper marked "embedded" with nothing stored
    #looks ready but returns nothing from every query
    db, paper = db_session_factory()

    class SilentlyEmptyClient:
        def embed_documents(self, texts):
            return []

    try:
        run_embedding_job(
            paper.id, owner_id="user_1", db=db, embeddings_client=SilentlyEmptyClient()
        )
    except RuntimeError:
        pass

    db.refresh(paper)
    assert paper.embedding_status == "failed"
    assert "0 vectors for 1 chunks" in paper.embedding_error


def test_a_partial_embedding_is_also_a_failure(db_session_factory):
    db, paper = db_session_factory()

    class ShortClient:
        def embed_documents(self, texts):
            return []  # fewer vectors than chunks

    try:
        run_embedding_job(paper.id, owner_id="user_1", db=db, embeddings_client=ShortClient())
    except RuntimeError:
        pass

    db.refresh(paper)
    assert paper.embedding_status == "failed"
