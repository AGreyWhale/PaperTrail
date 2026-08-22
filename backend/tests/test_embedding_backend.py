"""Which pipeline the enqueue dependency picks, and that both reach the same
wiring function. The Celery branch is asserted without a broker by checking
what it would call, not by calling it."""
import io

import pytest
from fastapi import BackgroundTasks

from app.api.papers import get_embedding_enqueue_fn
from app.core.config import get_settings
from app.main import app
from tests.pdf_helpers import make_test_pdf


def _processed_paper(client) -> str:
    paper_id = client.post(
        "/api/papers", json={"title": "A Paper", "authors": ["Someone"]}
    ).json()["id"]
    client.post(
        f"/api/papers/{paper_id}/file",
        files={"file": ("p.pdf", io.BytesIO(make_test_pdf(["Content. " * 40])), "application/pdf")},
    )
    client.post(f"/api/papers/{paper_id}/process")
    return paper_id


def test_background_tasks_backend_schedules_the_shared_wiring_function(monkeypatch):
    monkeypatch.setattr(get_settings(), "embedding_backend", "background_tasks")
    background_tasks = BackgroundTasks()

    enqueue = get_embedding_enqueue_fn(background_tasks)
    enqueue("paper-1", "user_1")

    # Scheduled, not executed — it runs after the response is sent.
    assert len(background_tasks.tasks) == 1
    task = background_tasks.tasks[0]
    assert task.func.__name__ == "embed_paper_now"
    assert task.args == ("paper-1", "user_1")


def test_celery_backend_does_not_touch_background_tasks(monkeypatch):
    monkeypatch.setattr(get_settings(), "embedding_backend", "celery")
    background_tasks = BackgroundTasks()

    enqueue = get_embedding_enqueue_fn(background_tasks)

    # The Celery closure is returned without scheduling anything in-process.
    assert background_tasks.tasks == []
    assert enqueue.__name__ == "_enqueue"


def test_both_backends_route_through_one_wiring_function():
    #Guards against the two paths drifting apart, which is the whole reason
    #embed_paper_now was extracted
    from app.workers import tasks

    assert tasks.embed_paper_task.__wrapped__.__code__.co_names.count("embed_paper_now") == 1


@pytest.mark.parametrize("backend", ["celery", "background_tasks"])
def test_embed_endpoint_returns_queued_under_either_backend(client, monkeypatch, backend):
    monkeypatch.setattr(get_settings(), "embedding_backend", backend)
    # The default conftest override stands in for the enqueue step, so this
    # asserts the endpoint contract, not the transport.
    paper_id = _processed_paper(client)

    response = client.post(f"/api/papers/{paper_id}/embed")

    assert response.status_code == 200
    assert response.json()["embedding_status"] == "queued"
