from app.core.auth import get_current_user_id
from app.main import app


def _create_paper(client, title: str = "A Paper") -> str:
    return client.post("/api/papers", json={"title": title, "authors": ["Someone"]}).json()["id"]


def _as(user: str) -> None:
    app.dependency_overrides[get_current_user_id] = lambda: user


def test_papers_start_unfavorited(client):
    paper_id = _create_paper(client)
    assert client.get(f"/api/papers/{paper_id}").json()["is_favorite"] is False


def test_favorite_toggles_both_ways(client):
    paper_id = _create_paper(client)

    assert client.patch(f"/api/papers/{paper_id}/favorite").json()["is_favorite"] is True
    assert client.patch(f"/api/papers/{paper_id}/favorite").json()["is_favorite"] is False


def test_favorite_404s_for_another_users_paper(client):
    _as("user_alice")
    paper_id = _create_paper(client, "Alice's Paper")

    _as("user_bob")
    assert client.patch(f"/api/papers/{paper_id}/favorite").status_code == 404


def test_adding_a_tag_creates_it_and_attaches_it(client):
    paper_id = _create_paper(client)

    body = client.post(f"/api/papers/{paper_id}/tags", json={"name": "Transformers"}).json()

    # Normalised to lowercase so "NLP" and "nlp" aren't two tags.
    assert [t["name"] for t in body["tags"]] == ["transformers"]
    assert [t["name"] for t in client.get("/api/tags").json()] == ["transformers"]


def test_same_tag_on_two_papers_is_reused_not_duplicated(client):
    first = _create_paper(client, "First")
    second = _create_paper(client, "Second")

    client.post(f"/api/papers/{first}/tags", json={"name": "nlp"})
    client.post(f"/api/papers/{second}/tags", json={"name": "nlp"})

    assert len(client.get("/api/tags").json()) == 1


def test_adding_the_same_tag_twice_is_idempotent(client):
    paper_id = _create_paper(client)
    client.post(f"/api/papers/{paper_id}/tags", json={"name": "nlp"})
    body = client.post(f"/api/papers/{paper_id}/tags", json={"name": "nlp"}).json()

    assert len(body["tags"]) == 1


def test_empty_tag_name_is_rejected(client):
    paper_id = _create_paper(client)
    assert client.post(f"/api/papers/{paper_id}/tags", json={"name": "   "}).status_code == 422


def test_removing_a_tag_detaches_it(client):
    paper_id = _create_paper(client)
    tagged = client.post(f"/api/papers/{paper_id}/tags", json={"name": "nlp"}).json()
    tag_id = tagged["tags"][0]["id"]

    body = client.delete(f"/api/papers/{paper_id}/tags/{tag_id}").json()

    assert body["tags"] == []
    # The tag itself survives for reuse elsewhere.
    assert len(client.get("/api/tags").json()) == 1


def test_papers_can_be_filtered_by_tag(client):
    tagged_id = _create_paper(client, "Tagged")
    _create_paper(client, "Untagged")
    tag_id = client.post(f"/api/papers/{tagged_id}/tags", json={"name": "nlp"}).json()["tags"][0]["id"]

    titles = [p["title"] for p in client.get(f"/api/papers?tag={tag_id}").json()]

    assert titles == ["Tagged"]


def test_tags_are_isolated_per_user(client):
    _as("user_alice")
    alice_paper = _create_paper(client, "Alice's Paper")
    client.post(f"/api/papers/{alice_paper}/tags", json={"name": "private"})

    _as("user_bob")
    assert client.get("/api/tags").json() == []
    assert client.post(f"/api/papers/{alice_paper}/tags", json={"name": "sneaky"}).status_code == 404
