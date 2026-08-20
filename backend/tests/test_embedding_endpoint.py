import io

from app.api.papers import get_embedding_enqueue_fn
from app.main import app
from tests.pdf_helpers import make_test_pdf


def _create_processed_paper(client) -> str:
    create_response = client.post(
        "/api/papers", json={"title": "A Test Paper", "authors": ["Someone"]}
    )
    paper_id = create_response.json()["id"]

    pdf_bytes = make_test_pdf(["Some content about a research topic. " * 10])
    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("paper.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    client.post(f"/api/papers/{paper_id}/process")
    return paper_id


def test_embed_requires_processed_paper(client):
    create_response = client.post(
        "/api/papers", json={"title": "Unprocessed Paper", "authors": ["Someone"]}
    )
    paper_id = create_response.json()["id"]

    response = client.post(f"/api/papers/{paper_id}/embed")

    assert response.status_code == 422


def test_embed_sets_status_to_queued_and_calls_enqueue_fn(client):
    calls = []
    app.dependency_overrides[get_embedding_enqueue_fn] = lambda: (
        lambda paper_id, owner_id: calls.append((paper_id, owner_id))
    )

    paper_id = _create_processed_paper(client)
    response = client.post(f"/api/papers/{paper_id}/embed")

    assert response.status_code == 200
    assert response.json()["embedding_status"] == "queued"
    assert calls == [(paper_id, "user_test123")]


def test_embed_nonexistent_paper_returns_404(client):
    response = client.post("/api/papers/00000000-0000-0000-0000-000000000000/embed")
    assert response.status_code == 404
