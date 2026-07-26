import io

from tests.pdf_helpers import make_test_pdf


def _create_and_upload_paper(client, pages_text: list[str]) -> str:
    create_response = client.post(
        "/api/papers", json={"title": "A Test Paper", "authors": ["Someone"]}
    )
    paper_id = create_response.json()["id"]

    pdf_bytes = make_test_pdf(pages_text)
    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("paper.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    return paper_id


def test_process_paper_creates_chunks(client):
    paper_id = _create_and_upload_paper(
        client,
        [
            "This paper introduces a new method for attention. " * 10,
            "Our experiments show significant improvements. " * 10,
        ],
    )

    response = client.post(f"/api/papers/{paper_id}/process")

    assert response.status_code == 200
    assert response.json()["processing_status"] == "processed"

    chunks_response = client.get(f"/api/papers/{paper_id}/chunks")
    chunks = chunks_response.json()
    assert len(chunks) > 0
    assert all(c["page_number"] in (1, 2) for c in chunks)
    assert all(c["token_count"] > 0 for c in chunks)


def test_process_paper_without_file_returns_422(client):
    create_response = client.post(
        "/api/papers", json={"title": "No File Paper", "authors": ["Someone"]}
    )
    paper_id = create_response.json()["id"]

    response = client.post(f"/api/papers/{paper_id}/process")

    assert response.status_code == 422


def test_process_nonexistent_paper_returns_404(client):
    response = client.post("/api/papers/00000000-0000-0000-0000-000000000000/process")
    assert response.status_code == 404


def test_reprocessing_replaces_chunks_not_duplicates(client):
    paper_id = _create_and_upload_paper(client, ["Some content about a research topic. " * 20])

    client.post(f"/api/papers/{paper_id}/process")
    first_count = len(client.get(f"/api/papers/{paper_id}/chunks").json())

    client.post(f"/api/papers/{paper_id}/process")
    second_count = len(client.get(f"/api/papers/{paper_id}/chunks").json())

    assert first_count == second_count
    assert first_count > 0


def test_chunks_are_isolated_per_owner(client):
    from app.core.auth import get_current_user_id
    from app.main import app

    app.dependency_overrides[get_current_user_id] = lambda: "user_alice"
    paper_id = _create_and_upload_paper(client, ["Alice's paper content here. " * 10])
    client.post(f"/api/papers/{paper_id}/process")

    app.dependency_overrides[get_current_user_id] = lambda: "user_bob"
    response = client.get(f"/api/papers/{paper_id}/chunks")
    assert response.status_code == 404
