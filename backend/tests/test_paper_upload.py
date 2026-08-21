import io

_MINIMAL_PDF = b"%PDF-1.4\n%%EOF"


def _create_paper(client) -> str:
    response = client.post(
        "/api/papers",
        json={"title": "A Paper", "authors": ["Someone"]},
    )
    return response.json()["id"]


def test_upload_attaches_file_to_paper(client):
    paper_id = _create_paper(client)

    response = client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("paper.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_file"] is True
    assert body["file_original_name"] == "paper.pdf"
    assert body["file_size_bytes"] == len(_MINIMAL_PDF)


def test_upload_rejects_content_without_pdf_magic_bytes(client):
    paper_id = _create_paper(client)

    response = client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("fake.pdf", io.BytesIO(b"not actually a pdf"), "application/pdf")},
    )

    assert response.status_code == 422


def test_upload_rejects_oversized_file(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_size_mb", 0)
    paper_id = _create_paper(client)

    response = client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("paper.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf")},
    )

    assert response.status_code == 413


def test_upload_to_nonexistent_paper_returns_404(client):
    response = client.post(
        "/api/papers/00000000-0000-0000-0000-000000000000/file",
        files={"file": ("paper.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf")},
    )

    assert response.status_code == 404


def test_upload_to_another_users_paper_returns_404(client):
    from app.core.auth import get_current_user_id
    from app.main import app

    app.dependency_overrides[get_current_user_id] = lambda: "user_alice"
    paper_id = _create_paper(client)

    app.dependency_overrides[get_current_user_id] = lambda: "user_bob"
    response = client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("paper.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf")},
    )

    assert response.status_code == 404


def test_file_actually_persists_to_storage(client, tmp_path):
    paper_id = _create_paper(client)

    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("paper.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf")},
    )

    stored_file = tmp_path / "papers" / paper_id / "original.pdf"
    assert stored_file.exists()
    assert stored_file.read_bytes() == _MINIMAL_PDF


def test_get_file_returns_the_uploaded_pdf_bytes(client):
    paper_id = _create_paper(client)
    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("paper.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf")},
    )

    response = client.get(f"/api/papers/{paper_id}/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == _MINIMAL_PDF


def test_get_file_404s_when_no_file_attached(client):
    paper_id = _create_paper(client)

    response = client.get(f"/api/papers/{paper_id}/file")

    assert response.status_code == 404


def test_get_file_404s_for_another_users_paper(client):
    from app.core.auth import get_current_user_id
    from app.main import app

    app.dependency_overrides[get_current_user_id] = lambda: "user_alice"
    paper_id = _create_paper(client)
    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("paper.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf")},
    )

    app.dependency_overrides[get_current_user_id] = lambda: "user_bob"
    response = client.get(f"/api/papers/{paper_id}/file")

    assert response.status_code == 404
