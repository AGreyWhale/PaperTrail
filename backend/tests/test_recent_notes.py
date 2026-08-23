from app.core.auth import get_current_user_id
from app.main import app


def _paper(client, title: str) -> str:
    return client.post("/api/papers", json={"title": title, "authors": ["Someone"]}).json()["id"]


def test_recent_notes_span_the_whole_library(client):
    first = _paper(client, "Paper One")
    second = _paper(client, "Paper Two")
    client.post(f"/api/papers/{first}/notes", json={"content": "Note on one"})
    client.post(f"/api/papers/{second}/notes", json={"content": "Note on two"})

    notes = client.get("/api/notes/recent").json()

    # Not scoped to a single paper, unlike /papers/{id}/notes.
    assert {n["paper_title"] for n in notes} == {"Paper One", "Paper Two"}


def test_recent_notes_are_newest_first(client):
    paper_id = _paper(client, "A Paper")
    client.post(f"/api/papers/{paper_id}/notes", json={"content": "Older"})
    client.post(f"/api/papers/{paper_id}/notes", json={"content": "Newer"})

    assert [n["content"] for n in client.get("/api/notes/recent").json()] == ["Newer", "Older"]


def test_recent_notes_carry_the_page_so_the_panel_can_deep_link(client):
    paper_id = _paper(client, "A Paper")
    client.post(
        f"/api/papers/{paper_id}/notes",
        json={"content": "Worth revisiting", "quoted_text": "A passage.", "page_number": 7},
    )

    note = client.get("/api/notes/recent").json()[0]

    assert note["page_number"] == 7
    assert note["paper_id"] == paper_id
    assert note["quoted_text"] == "A passage."


def test_recent_notes_respect_the_limit(client):
    paper_id = _paper(client, "A Paper")
    for n in range(4):
        client.post(f"/api/papers/{paper_id}/notes", json={"content": f"Note {n}"})

    assert len(client.get("/api/notes/recent", params={"limit": 2}).json()) == 2


def test_recent_route_is_not_parsed_as_a_note_id(client):
    # /{note_id} would swallow this path if it were declared first.
    assert client.get("/api/notes/recent").status_code == 200


def test_recent_notes_are_isolated_per_user(client):
    app.dependency_overrides[get_current_user_id] = lambda: "user_alice"
    alice_paper = _paper(client, "Alice's Paper")
    client.post(f"/api/papers/{alice_paper}/notes", json={"content": "Alice's private note"})

    app.dependency_overrides[get_current_user_id] = lambda: "user_bob"
    assert client.get("/api/notes/recent").json() == []
