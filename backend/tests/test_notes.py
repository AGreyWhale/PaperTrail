from app.core.auth import get_current_user_id
from app.main import app


def _create_paper(client, title: str = "A Paper") -> str:
    return client.post("/api/papers", json={"title": title, "authors": ["Someone"]}).json()["id"]


def _as(user: str) -> None:
    app.dependency_overrides[get_current_user_id] = lambda: user


def test_a_freehand_note_has_no_quote(client):
    paper_id = _create_paper(client)

    body = client.post(f"/api/papers/{paper_id}/notes", json={"content": "My own thought"}).json()

    assert body["content"] == "My own thought"
    assert body["quoted_text"] is None
    assert body["page_number"] is None


def test_a_note_can_carry_the_passage_it_came_from(client):
    paper_id = _create_paper(client)

    body = client.post(
        f"/api/papers/{paper_id}/notes",
        json={
            "content": "Worth revisiting",
            "quoted_text": "The model uses a transformer encoder.",
            "page_number": 4,
        },
    ).json()

    assert body["quoted_text"] == "The model uses a transformer encoder."
    assert body["page_number"] == 4


def test_empty_note_content_is_rejected(client):
    paper_id = _create_paper(client)
    assert client.post(f"/api/papers/{paper_id}/notes", json={"content": "   "}).status_code == 422


def test_notes_come_back_newest_first(client):
    paper_id = _create_paper(client)
    client.post(f"/api/papers/{paper_id}/notes", json={"content": "First"})
    client.post(f"/api/papers/{paper_id}/notes", json={"content": "Second"})

    assert [n["content"] for n in client.get(f"/api/papers/{paper_id}/notes").json()] == [
        "Second",
        "First",
    ]


def test_notes_can_be_edited(client):
    paper_id = _create_paper(client)
    note_id = client.post(f"/api/papers/{paper_id}/notes", json={"content": "Draft"}).json()["id"]

    body = client.patch(f"/api/notes/{note_id}", json={"content": "Revised"}).json()

    assert body["content"] == "Revised"


def test_notes_can_be_deleted(client):
    paper_id = _create_paper(client)
    note_id = client.post(f"/api/papers/{paper_id}/notes", json={"content": "Temp"}).json()["id"]

    assert client.delete(f"/api/notes/{note_id}").status_code == 204
    assert client.get(f"/api/papers/{paper_id}/notes").json() == []


def test_notes_on_a_missing_paper_404(client):
    assert (
        client.post(
            "/api/papers/00000000-0000-0000-0000-000000000000/notes", json={"content": "x"}
        ).status_code
        == 404
    )


def test_bob_cannot_see_or_touch_alices_notes(client):
    _as("user_alice")
    alice_paper = _create_paper(client, "Alice's Paper")
    note_id = client.post(
        f"/api/papers/{alice_paper}/notes", json={"content": "Alice's private note"}
    ).json()["id"]

    _as("user_bob")
    assert client.get(f"/api/papers/{alice_paper}/notes").status_code == 404
    assert client.patch(f"/api/notes/{note_id}", json={"content": "hijacked"}).status_code == 404
    assert client.delete(f"/api/notes/{note_id}").status_code == 404


def test_a_highlight_is_a_note_with_a_quote_and_no_words_yet(client):
    paper_id = _create_paper(client)

    body = client.post(
        f"/api/papers/{paper_id}/notes",
        json={"quoted_text": "A striking passage.", "page_number": 3, "color": "yellow"},
    ).json()

    # Blank content is fine when something was actually highlighted.
    assert body["content"] == ""
    assert body["color"] == "yellow"
    assert body["quoted_text"] == "A striking passage."


def test_a_note_with_neither_content_nor_quote_is_rejected(client):
    paper_id = _create_paper(client)
    assert client.post(f"/api/papers/{paper_id}/notes", json={"content": "  "}).status_code == 422


def test_a_highlight_can_have_words_added_later(client):
    paper_id = _create_paper(client)
    note_id = client.post(
        f"/api/papers/{paper_id}/notes",
        json={"quoted_text": "A passage.", "page_number": 1, "color": "blue"},
    ).json()["id"]

    body = client.patch(f"/api/notes/{note_id}", json={"content": "Now annotated"}).json()

    assert body["content"] == "Now annotated"
    assert body["color"] == "blue"
