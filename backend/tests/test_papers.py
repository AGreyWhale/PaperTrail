def test_add_and_get_paper(client):
    response = client.post(
        "/api/papers",
        json={
            "title": "Attention Is All You Need",
            "authors": ["Vaswani", "Shazeer"],
            "venue": "NeurIPS",
            "year": 2017,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Attention Is All You Need"
    assert body["authors"] == ["Vaswani", "Shazeer"]

    paper_id = body["id"]
    get_response = client.get(f"/api/papers/{paper_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == paper_id


def test_list_papers_empty(client):
    response = client.get("/api/papers")
    assert response.status_code == 200
    assert response.json() == []


def test_add_paper_rejects_empty_title(client):
    response = client.post(
        "/api/papers",
        json={"title": "   ", "authors": ["Someone"]},
    )
    assert response.status_code == 422


def test_get_nonexistent_paper_returns_404(client):
    response = client.get("/api/papers/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_papers_are_isolated_per_user(client):
    from app.core.auth import get_current_user_id
    from app.main import app

    app.dependency_overrides[get_current_user_id] = lambda: "user_alice"
    create_response = client.post(
        "/api/papers",
        json={"title": "Alice's Paper", "authors": ["Alice"]},
    )
    paper_id = create_response.json()["id"]

    app.dependency_overrides[get_current_user_id] = lambda: "user_bob"
    # Bob's list shouldn't include Alice's paper...
    list_response = client.get("/api/papers")
    assert list_response.json() == []
    # ...and Bob can't fetch it directly either (404, not 403 — we
    # don't want to reveal that a paper with this ID exists at all).
    get_response = client.get(f"/api/papers/{paper_id}")
    assert get_response.status_code == 404
