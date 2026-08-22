import io
import uuid

from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.papers import get_embedding_enqueue_fn, get_chunk_repository, get_embeddings_client
from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.main import app
from app.workers.embedding_job import run_embedding_job
from tests.fakes import FakeChunkSearch, FakeEmbeddingsClient
from tests.pdf_helpers import make_test_pdf


def _setup_embedded_paper(client) -> str:
    #Creates, uploads, processes and embeds a paper with fakes throughout,
    #running the job inline instead of through Celery
    fake_embeddings_client = FakeEmbeddingsClient()
    app.dependency_overrides[get_embeddings_client] = lambda: fake_embeddings_client
    # Resolved with the request's own session, so the fake reads the same DB.
    app.dependency_overrides[get_chunk_repository] = lambda db=Depends(get_db): FakeChunkSearch(db)

    def _run_synchronously(paper_id: str, owner_id: str) -> None:
        # Goes through the app's own get_db override, so the job runs
        # against the same in-memory DB the test client is using.
        db_generator = app.dependency_overrides[get_db]()
        db = next(db_generator)
        try:
            run_embedding_job(
                uuid.UUID(paper_id),
                owner_id=owner_id,
                db=db,
                embeddings_client=fake_embeddings_client,
            )
        finally:
            db_generator.close()

    app.dependency_overrides[get_embedding_enqueue_fn] = lambda: _run_synchronously

    create_response = client.post(
        "/api/papers", json={"title": "A Test Paper", "authors": ["Someone"]}
    )
    paper_id = create_response.json()["id"]

    pdf_bytes = make_test_pdf(["Attention mechanisms are the core idea explained here."])
    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("paper.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    client.post(f"/api/papers/{paper_id}/process")
    client.post(f"/api/papers/{paper_id}/embed")

    return paper_id


def test_similar_returns_matching_chunk(client):
    paper_id = _setup_embedded_paper(client)

    response = client.get(
        f"/api/papers/{paper_id}/similar",
        params={"query": "Attention mechanisms are the core idea explained here."},
    )

    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert "Attention mechanisms" in results[0]["text"]
    assert results[0]["score"] > 0.999


def test_similar_requires_embedded_paper(client):
    # Faked even though this 422s before reaching the similarity query:
    # FastAPI builds every dependency up front.
    app.dependency_overrides[get_embeddings_client] = lambda: FakeEmbeddingsClient()
    app.dependency_overrides[get_chunk_repository] = lambda db=Depends(get_db): FakeChunkSearch(db)

    create_response = client.post(
        "/api/papers", json={"title": "Not Embedded Paper", "authors": ["Someone"]}
    )
    paper_id = create_response.json()["id"]

    response = client.get(f"/api/papers/{paper_id}/similar", params={"query": "anything"})

    assert response.status_code == 422


def test_similar_requires_authentication():
    # No fakes registered on purpose — auth is resolved before the
    # search service, so this 401s without loading the real model.
    app.dependency_overrides.pop(get_current_user_id, None)
    with TestClient(app) as unauth_client:
        response = unauth_client.get(
            "/api/papers/00000000-0000-0000-0000-000000000000/similar",
            params={"query": "anything"},
        )
    assert response.status_code == 401
    app.dependency_overrides.clear()
