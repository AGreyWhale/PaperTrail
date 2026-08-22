import io

import chromadb

from app.api.papers import get_optional_vector_store
from app.core.auth import get_current_user_id
from app.main import app
from app.vectorstore.client import VectorStore
from tests.pdf_helpers import make_test_pdf

_PDF = make_test_pdf(["Some content to process into chunks."])


def _create_paper(client, title: str = "A Paper") -> str:
    return client.post("/api/papers", json={"title": title, "authors": ["Someone"]}).json()["id"]


def _with_file(client, paper_id: str) -> None:
    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("p.pdf", io.BytesIO(_PDF), "application/pdf")},
    )


def test_deleting_a_paper_removes_it_from_the_library(client):
    paper_id = _create_paper(client)

    assert client.delete(f"/api/papers/{paper_id}").status_code == 204
    assert client.get(f"/api/papers/{paper_id}").status_code == 404
    assert client.get("/api/papers").json() == []


def test_deleting_a_paper_takes_its_chunks_and_notes_with_it(client):
    paper_id = _create_paper(client)
    _with_file(client, paper_id)
    client.post(f"/api/papers/{paper_id}/process")
    client.post(f"/api/papers/{paper_id}/notes", json={"content": "A note"})
    assert len(client.get(f"/api/papers/{paper_id}/chunks").json()) > 0

    client.delete(f"/api/papers/{paper_id}")

    # Both cascade at the FK level; 404 because the paper itself is gone.
    assert client.get(f"/api/papers/{paper_id}/chunks").status_code == 404
    assert client.get(f"/api/papers/{paper_id}/notes").status_code == 404


def test_deleting_a_paper_removes_the_stored_file(client, tmp_path):
    paper_id = _create_paper(client)
    _with_file(client, paper_id)
    stored = tmp_path / "papers" / paper_id / "original.pdf"
    assert stored.exists()

    client.delete(f"/api/papers/{paper_id}")

    # The bytes live outside Postgres, so nothing cascades them away.
    assert not stored.exists()


def test_deleting_a_paper_clears_its_vectors(client):
    store = VectorStore(chromadb.EphemeralClient())
    app.dependency_overrides[get_optional_vector_store] = lambda: store
    paper_id = _create_paper(client)

    import uuid as _uuid

    store.upsert_chunks(
        owner_id="user_test123",
        paper_id=_uuid.UUID(paper_id),
        chunk_ids=[_uuid.uuid4()],
        texts=["Some embedded content."],
        embeddings=[[0.1] * 8],
        page_numbers=[1],
    )

    client.delete(f"/api/papers/{paper_id}")

    assert (
        store.query_within_paper(
            owner_id="user_test123", paper_id=_uuid.UUID(paper_id), query_embedding=[0.1] * 8
        )
        == []
    )


def test_deletion_survives_an_unreachable_vector_store(client):
    #Chroma being down must not strand a paper the user asked to delete
    app.dependency_overrides[get_optional_vector_store] = lambda: None
    paper_id = _create_paper(client)

    assert client.delete(f"/api/papers/{paper_id}").status_code == 204


def test_bob_cannot_delete_alices_paper(client):
    app.dependency_overrides[get_current_user_id] = lambda: "user_alice"
    paper_id = _create_paper(client, "Alice's Paper")

    app.dependency_overrides[get_current_user_id] = lambda: "user_bob"
    assert client.delete(f"/api/papers/{paper_id}").status_code == 404

    app.dependency_overrides[get_current_user_id] = lambda: "user_alice"
    assert client.get(f"/api/papers/{paper_id}").status_code == 200
