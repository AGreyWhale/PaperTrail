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


# --- the ONNX embeddings client ---

def test_embeddings_client_uses_cls_pooling_not_mean():
    #BGE pools the CLS token. Mean pooling scores ~0.95 against the real model
    #— close enough to look right while quietly degrading every retrieval, so
    #this pins the choice rather than trusting a comment
    import numpy as np

    from app.integrations.embeddings.local_client import EmbeddingsClient

    class FakeSession:
        def get_inputs(self):
            return [type("S", (), {"name": "input_ids"}), type("S", (), {"name": "attention_mask"})]

        def run(self, _outputs, feed):
            # CLS token is a clean unit vector; later tokens are noise that
            # would drag the result off if they were averaged in.
            batch = feed["input_ids"].shape[0]
            hidden = np.zeros((batch, 3, 4), dtype=np.float32)
            hidden[:, 0] = [1.0, 0.0, 0.0, 0.0]
            hidden[:, 1] = [0.0, 5.0, 0.0, 0.0]
            hidden[:, 2] = [0.0, 0.0, 5.0, 0.0]
            return [hidden]

    class FakeEncoding:
        ids = [1, 2, 3]
        attention_mask = [1, 1, 1]
        type_ids = [0, 0, 0]

    class FakeTokenizer:
        def encode_batch(self, texts):
            return [FakeEncoding() for _ in texts]

    client = EmbeddingsClient(model=(FakeSession(), FakeTokenizer()))

    assert client.embed_documents(["anything"])[0] == [1.0, 0.0, 0.0, 0.0]


def test_embeddings_client_does_not_load_anything_until_used():
    #Every request that builds a service constructs one of these; most never
    #embed. Loading at construction is what put the API process over its limit
    import sys

    from app.integrations.embeddings.local_client import EmbeddingsClient

    EmbeddingsClient(model_name="BAAI/bge-small-en-v1.5")

    assert "torch" not in sys.modules


def test_embed_documents_short_circuits_on_an_empty_list():
    from app.integrations.embeddings.local_client import EmbeddingsClient

    # Must not touch the model at all — there's nothing to encode.
    assert EmbeddingsClient(model=None).embed_documents([]) == []
