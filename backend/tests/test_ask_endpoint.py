import io
import uuid

import chromadb
from fastapi.testclient import TestClient

from app.api.papers import (
    get_embedding_enqueue_fn,
    get_embeddings_client,
    get_llm_client,
    get_vector_store,
)
from app.core.auth import get_current_user_id
from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.vectorstore.client import VectorStore
from app.workers.embedding_job import run_embedding_job
from tests.fakes import FakeEmbeddingsClient, FakeLLMClient
from tests.pdf_helpers import make_test_pdf


def _setup_embedded_paper(client, *, llm_client) -> str:
    #Same setup as test_search_endpoint's helper, plus a fake LLM
    fake_embeddings_client = FakeEmbeddingsClient()
    fake_vector_store = VectorStore(chromadb.EphemeralClient())
    app.dependency_overrides[get_embeddings_client] = lambda: fake_embeddings_client
    app.dependency_overrides[get_vector_store] = lambda: fake_vector_store
    app.dependency_overrides[get_llm_client] = lambda: llm_client

    def _run_synchronously(paper_id: str, owner_id: str) -> None:
        db_generator = app.dependency_overrides[get_db]()
        db = next(db_generator)
        try:
            run_embedding_job(
                uuid.UUID(paper_id),
                owner_id=owner_id,
                db=db,
                embeddings_client=fake_embeddings_client,
                vector_store=fake_vector_store,
            )
        finally:
            db_generator.close()

    app.dependency_overrides[get_embedding_enqueue_fn] = lambda: _run_synchronously

    create_response = client.post(
        "/api/papers", json={"title": "A Test Paper", "authors": ["Someone"]}
    )
    paper_id = create_response.json()["id"]

    pdf_bytes = make_test_pdf(["The model uses a transformer architecture for encoding."])
    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("paper.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    client.post(f"/api/papers/{paper_id}/process")
    client.post(f"/api/papers/{paper_id}/embed")

    return paper_id


def test_ask_returns_answer_with_citations(client):
    llm_client = FakeLLMClient(answer="They used a transformer architecture. (p. 1)")
    paper_id = _setup_embedded_paper(client, llm_client=llm_client)

    response = client.post(
        f"/api/papers/{paper_id}/ask", json={"question": "What architecture did they use?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "They used a transformer architecture. (p. 1)"
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["page_number"] == 1


def test_ask_requires_embedded_paper(client):
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient()
    app.dependency_overrides[get_embeddings_client] = lambda: FakeEmbeddingsClient()
    app.dependency_overrides[get_vector_store] = lambda: VectorStore(chromadb.EphemeralClient())

    create_response = client.post(
        "/api/papers", json={"title": "Not Embedded", "authors": ["Someone"]}
    )
    paper_id = create_response.json()["id"]

    response = client.post(f"/api/papers/{paper_id}/ask", json={"question": "Anything?"})

    assert response.status_code == 422


def test_ask_rejects_empty_question(client):
    llm_client = FakeLLMClient()
    paper_id = _setup_embedded_paper(client, llm_client=llm_client)

    response = client.post(f"/api/papers/{paper_id}/ask", json={"question": "   "})

    assert response.status_code == 422
    assert len(llm_client.calls) == 0  # never should have reached the LLM


def test_ask_returns_503_without_llm_key(client, monkeypatch):
    # No override for get_llm_client, so this hits the real factory,
    # which should refuse cleanly when no key is configured. Cleared on
    # the cached Settings so a real key in .env can't mask the failure.
    monkeypatch.setattr(get_settings(), "llm_api_key", "")
    app.dependency_overrides[get_embeddings_client] = lambda: FakeEmbeddingsClient()
    app.dependency_overrides[get_vector_store] = lambda: VectorStore(chromadb.EphemeralClient())

    create_response = client.post(
        "/api/papers", json={"title": "Some Paper", "authors": ["Someone"]}
    )
    paper_id = create_response.json()["id"]

    response = client.post(f"/api/papers/{paper_id}/ask", json={"question": "Anything?"})

    assert response.status_code == 503


def test_ask_requires_authentication():
    # No fakes registered on purpose — auth is resolved before the RAG
    # service is built, so this 401s without touching the LLM at all.
    app.dependency_overrides.pop(get_current_user_id, None)
    with TestClient(app) as unauth_client:
        response = unauth_client.post(
            "/api/papers/00000000-0000-0000-0000-000000000000/ask",
            json={"question": "Anything?"},
        )
    assert response.status_code == 401
    app.dependency_overrides.clear()
