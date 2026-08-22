from app.core.auth import get_current_user_id
from app.main import app


def _create_paper(client, title: str = "A Paper") -> str:
    return client.post("/api/papers", json={"title": title, "authors": ["Someone"]}).json()["id"]


def _create_collection(client, name: str = "To Read") -> str:
    return client.post("/api/collections", json={"name": name}).json()["id"]


def _as(user: str) -> None:
    app.dependency_overrides[get_current_user_id] = lambda: user


def test_creating_a_collection_starts_empty(client):
    body = client.post("/api/collections", json={"name": "To Read"}).json()

    assert body["name"] == "To Read"
    assert body["paper_count"] == 0


def test_empty_collection_name_is_rejected(client):
    assert client.post("/api/collections", json={"name": "  "}).status_code == 422


def test_listing_collections_includes_paper_counts(client):
    collection_id = _create_collection(client)
    client.post(f"/api/collections/{collection_id}/papers/{_create_paper(client, 'One')}")
    client.post(f"/api/collections/{collection_id}/papers/{_create_paper(client, 'Two')}")

    assert client.get("/api/collections").json()[0]["paper_count"] == 2


def test_a_paper_can_live_in_several_collections(client):
    paper_id = _create_paper(client)
    first = _create_collection(client, "To Read")
    second = _create_collection(client, "Cited")

    client.post(f"/api/collections/{first}/papers/{paper_id}")
    client.post(f"/api/collections/{second}/papers/{paper_id}")

    assert [c["paper_count"] for c in client.get("/api/collections").json()] == [1, 1]


def test_adding_the_same_paper_twice_is_idempotent(client):
    paper_id = _create_paper(client)
    collection_id = _create_collection(client)

    client.post(f"/api/collections/{collection_id}/papers/{paper_id}")
    body = client.post(f"/api/collections/{collection_id}/papers/{paper_id}").json()

    assert body["paper_count"] == 1


def test_removing_a_paper_leaves_the_paper_itself_alone(client):
    paper_id = _create_paper(client)
    collection_id = _create_collection(client)
    client.post(f"/api/collections/{collection_id}/papers/{paper_id}")

    client.delete(f"/api/collections/{collection_id}/papers/{paper_id}")

    assert client.get(f"/api/collections/{collection_id}/papers").json() == []
    assert client.get(f"/api/papers/{paper_id}").status_code == 200


def test_deleting_a_collection_leaves_its_papers_alone(client):
    paper_id = _create_paper(client)
    collection_id = _create_collection(client)
    client.post(f"/api/collections/{collection_id}/papers/{paper_id}")

    assert client.delete(f"/api/collections/{collection_id}").status_code == 204
    assert client.get(f"/api/papers/{paper_id}").status_code == 200


def test_collections_are_isolated_per_user(client):
    _as("user_alice")
    alice_collection = _create_collection(client, "Alice's Shelf")
    alice_paper = _create_paper(client, "Alice's Paper")

    _as("user_bob")
    assert client.get("/api/collections").json() == []
    assert client.get(f"/api/collections/{alice_collection}/papers").status_code == 404
    assert client.delete(f"/api/collections/{alice_collection}").status_code == 404
    assert (
        client.post(f"/api/collections/{alice_collection}/papers/{alice_paper}").status_code == 404
    )
