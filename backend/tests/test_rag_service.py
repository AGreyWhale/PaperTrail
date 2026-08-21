import chromadb
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.integrations.llm.client import LLMUnavailableError
from app.models.chunk import Chunk
from app.models.paper import Paper
from app.repositories.paper_repository import PaperRepository
from app.services.rag_service import RagService
from app.services.search_service import SearchService
from app.vectorstore.client import VectorStore
from app.workers.embedding_job import run_embedding_job
from tests.fakes import FakeEmbeddingsClient, FakeLLMClient


def _make_db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _make_embedded_paper(*, owner_id: str, chunk_texts: list[str]):
    db = _make_db_session()

    paper = Paper(
        owner_id=owner_id, title="Test Paper", authors="A. Author", processing_status="processed"
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    for i, text in enumerate(chunk_texts):
        db.add(
            Chunk(paper_id=paper.id, chunk_index=i, page_number=i + 1, text=text, token_count=10)
        )
    db.commit()

    embeddings_client = FakeEmbeddingsClient()
    vector_store = VectorStore(chromadb.EphemeralClient())
    run_embedding_job(
        paper.id,
        owner_id=owner_id,
        db=db,
        embeddings_client=embeddings_client,
        vector_store=vector_store,
    )
    db.refresh(paper)

    return paper, SearchService(PaperRepository(db), embeddings_client, vector_store)


def test_answer_question_returns_answer_and_citations():
    paper, search_service = _make_embedded_paper(
        owner_id="user_1", chunk_texts=["The model uses a transformer architecture."]
    )
    service = RagService(search_service, FakeLLMClient(answer="They used a transformer. (p. 1)"))

    result = service.answer_question(
        paper.id, owner_id="user_1", question="What architecture did they use?"
    )

    assert result["answer"] == "They used a transformer. (p. 1)"
    assert len(result["citations"]) >= 1
    assert result["citations"][0]["page_number"] == 1


def test_answer_question_grounds_prompt_in_retrieved_chunks():
    paper, search_service = _make_embedded_paper(
        owner_id="user_1", chunk_texts=["The model uses a transformer architecture."]
    )
    llm_client = FakeLLMClient()
    service = RagService(search_service, llm_client)

    service.answer_question(
        paper.id, owner_id="user_1", question="What architecture did they use?"
    )

    assert len(llm_client.calls) == 1
    assert "transformer architecture" in llm_client.calls[0]["user"]
    assert "page 1" in llm_client.calls[0]["user"]
    # The system prompt is what enforces grounding, so check it was sent.
    assert "ONLY the excerpts" in llm_client.calls[0]["system"]


def test_answer_question_rejects_empty_question():
    paper, search_service = _make_embedded_paper(owner_id="user_1", chunk_texts=["Some content."])
    service = RagService(search_service, FakeLLMClient())

    with pytest.raises(HTTPException) as exc_info:
        service.answer_question(paper.id, owner_id="user_1", question="   ")

    assert exc_info.value.status_code == 422


def test_answer_question_requires_embedded_paper():
    db = _make_db_session()
    paper = Paper(owner_id="user_1", title="Unembedded Paper", authors="A. Author")
    db.add(paper)
    db.commit()
    db.refresh(paper)

    search_service = SearchService(
        PaperRepository(db), FakeEmbeddingsClient(), VectorStore(chromadb.EphemeralClient())
    )
    service = RagService(search_service, FakeLLMClient())

    with pytest.raises(HTTPException) as exc_info:
        service.answer_question(paper.id, owner_id="user_1", question="Anything?")

    assert exc_info.value.status_code == 422


def test_answer_question_maps_llm_failure_to_502():
    paper, search_service = _make_embedded_paper(owner_id="user_1", chunk_texts=["Some content."])

    class BrokenLLMClient:
        def complete(self, *, system, user):
            raise LLMUnavailableError("The model `nope` does not exist")

    service = RagService(search_service, BrokenLLMClient())

    with pytest.raises(HTTPException) as exc_info:
        service.answer_question(paper.id, owner_id="user_1", question="Anything?")

    assert exc_info.value.status_code == 502
    # The provider's own wording should survive to the client.
    assert "does not exist" in exc_info.value.detail
