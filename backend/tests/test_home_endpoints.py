from app.api.papers import get_optional_llm_client
from app.main import app
from tests.fakes import FakeLLMClient


def _create_paper(client, title: str) -> str:
    return client.post("/api/papers", json={"title": title, "authors": ["Someone"]}).json()["id"]


def test_continue_reading_is_empty_until_a_paper_is_opened(client):
    _create_paper(client, "Unopened Paper")

    assert client.get("/api/papers/continue-reading").json() == []


def test_opening_a_paper_records_progress(client):
    paper_id = _create_paper(client, "A Paper")

    response = client.post(f"/api/papers/{paper_id}/opened", params={"page": 7})

    assert response.status_code == 200
    assert response.json()["last_page"] == 7
    assert response.json()["last_opened_at"] is not None


def test_continue_reading_is_most_recent_first(client):
    first = _create_paper(client, "Read First")
    second = _create_paper(client, "Read Second")

    client.post(f"/api/papers/{first}/opened", params={"page": 2})
    client.post(f"/api/papers/{second}/opened", params={"page": 5})

    titles = [p["title"] for p in client.get("/api/papers/continue-reading").json()]
    assert titles == ["Read Second", "Read First"]


def test_continue_reading_route_is_not_parsed_as_a_paper_id(client):
    # /{paper_id} would swallow this path if it were declared first.
    assert client.get("/api/papers/continue-reading").status_code == 200


def test_reopening_moves_a_paper_back_to_the_front(client):
    first = _create_paper(client, "Older")
    second = _create_paper(client, "Newer")
    client.post(f"/api/papers/{first}/opened", params={"page": 1})
    client.post(f"/api/papers/{second}/opened", params={"page": 1})
    client.post(f"/api/papers/{first}/opened", params={"page": 3})

    titles = [p["title"] for p in client.get("/api/papers/continue-reading").json()]
    assert titles == ["Older", "Newer"]


def test_suggested_questions_are_generated_then_cached(client):
    llm_client = FakeLLMClient(
        answer="1. What method is used?\n2. How was it evaluated?\n- What are the limits?"
    )
    app.dependency_overrides[get_optional_llm_client] = lambda: llm_client

    paper_id = _create_paper(client, "A Paper")
    # Needs chunks to have something to summarise, so process a real PDF.
    import io

    from tests.pdf_helpers import make_test_pdf

    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("p.pdf", io.BytesIO(make_test_pdf(["Transformer encoders. " * 20])), "application/pdf")},
    )
    client.post(f"/api/papers/{paper_id}/process")

    first = client.get(f"/api/papers/{paper_id}/suggested-questions").json()
    assert first == ["What method is used?", "How was it evaluated?", "What are the limits?"]

    second = client.get(f"/api/papers/{paper_id}/suggested-questions").json()
    assert second == first
    assert len(llm_client.calls) == 1  # cached, not regenerated


def test_suggested_questions_degrade_to_empty_without_an_llm_key(client):
    app.dependency_overrides[get_optional_llm_client] = lambda: None
    paper_id = _create_paper(client, "A Paper")

    response = client.get(f"/api/papers/{paper_id}/suggested-questions")

    # A missing key must not break the home page.
    assert response.status_code == 200
    assert response.json() == []
