import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.chunk import Chunk
from app.models.paper import Paper
from app.repositories.paper_repository import PaperRepository
from app.services.multi_ask_service import MultiAskService, build_prompt
from app.services.search_service import SearchService
from app.workers.embedding_job import run_embedding_job
from tests.fakes import FakeChunkSearch, FakeEmbeddingsClient, FakeLLMClient


def _library(specs, *, owner_id="user_1"):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    embeddings_client = FakeEmbeddingsClient()
    papers = []

    for title, text, embed in specs:
        paper = Paper(
            owner_id=owner_id, title=title, authors="Jane Smith, Bob Lee",
            processing_status="processed",
        )
        db.add(paper)
        db.commit()
        db.refresh(paper)
        db.add(Chunk(paper_id=paper.id, chunk_index=0, page_number=4, text=text, token_count=10))
        db.commit()
        if embed:
            run_embedding_job(paper.id, owner_id=owner_id, db=db, embeddings_client=embeddings_client)
        db.refresh(paper)
        papers.append(paper)

    search = SearchService(PaperRepository(db), embeddings_client, FakeChunkSearch(db))
    return db, papers, search


def _service(db, search, llm=None):
    return MultiAskService(PaperRepository(db), search, llm or FakeLLMClient())


def test_answer_draws_on_every_selected_paper():
    db, papers, search = _library(
        [("Paper A", "Transformers use self-attention.", True),
         ("Paper B", "Graph networks aggregate neighbours.", True)]
    )
    llm = FakeLLMClient(answer="Both use learned aggregation. (Smith et al., p. 4)")
    result = _service(db, search, llm).ask(
        [p.id for p in papers], owner_id="user_1", question="How do these models aggregate?"
    )

    assert result.answer.startswith("Both use")
    # Excerpts from both papers reached the prompt.
    assert "self-attention" in llm.calls[0]["user"]
    assert "aggregate neighbours" in llm.calls[0]["user"]


def test_citations_name_the_paper_not_just_the_page():
    db, papers, search = _library(
        [("Paper A", "Content one.", True), ("Paper B", "Content two.", True)]
    )
    result = _service(db, search).ask(
        [p.id for p in papers], owner_id="user_1", question="Anything?"
    )

    titles = {c.paper_title for c in result.citations}
    assert titles == {"Paper A", "Paper B"}
    assert all(c.citation == "Smith et al." for c in result.citations)
    assert all(c.page_number == 4 for c in result.citations)


def test_prompt_requires_paper_level_citations():
    db, papers, search = _library(
        [("A", "Content one.", True), ("B", "Content two.", True)]
    )
    llm = FakeLLMClient()
    _service(db, search, llm).ask([p.id for p in papers], owner_id="user_1", question="Anything?")

    system = llm.calls[0]["system"]
    assert "ONLY the excerpts" in system
    assert "page number alone is not enough" in system.lower()
    # Tables were dropping citations into column headers and losing the page.
    assert "every cell still needs its page citation" in system


def test_the_question_is_what_drives_retrieval():
    #Compare and review use broad survey probes; ask must use the question
    db, papers, search = _library(
        [("A", "Content one.", True), ("B", "Content two.", True)]
    )
    llm = FakeLLMClient()
    _service(db, search, llm).ask(
        [p.id for p in papers], owner_id="user_1", question="What about pooling?"
    )

    assert "What about pooling?" in llm.calls[0]["user"]


def test_build_prompt_is_pure_and_includes_the_question():
    assert "Question: Why?" in build_prompt("Why?", [])


def test_an_empty_question_is_rejected_before_the_llm():
    db, papers, search = _library([("A", "x.", True), ("B", "y.", True)])
    llm = FakeLLMClient()

    with pytest.raises(HTTPException) as exc:
        _service(db, search, llm).ask([p.id for p in papers], owner_id="user_1", question="  ")

    assert exc.value.status_code == 422
    assert llm.calls == []


def test_fewer_than_two_papers_is_rejected():
    db, papers, search = _library([("Only One", "Content.", True)])

    with pytest.raises(HTTPException) as exc:
        _service(db, search).ask([papers[0].id], owner_id="user_1", question="Anything?")

    assert exc.value.status_code == 422


def test_unembedded_papers_are_rejected():
    db, papers, search = _library([("Ready", "x.", True), ("Not ready", "y.", False)])

    with pytest.raises(HTTPException) as exc:
        _service(db, search).ask([p.id for p in papers], owner_id="user_1", question="Anything?")

    assert exc.value.status_code == 422
    assert "Not ready" in exc.value.detail


def test_papers_owned_by_someone_else_are_refused():
    db, papers, search = _library(
        [("Alice A", "x.", True), ("Alice B", "y.", True)], owner_id="user_alice"
    )

    with pytest.raises(HTTPException) as exc:
        _service(db, search).ask([p.id for p in papers], owner_id="user_bob", question="Anything?")

    assert exc.value.status_code == 404


def test_a_forged_id_mixed_in_is_refused():
    db, papers, search = _library([("A", "x.", True), ("B", "y.", True)])

    with pytest.raises(HTTPException) as exc:
        _service(db, search).ask(
            [papers[0].id, papers[1].id, uuid.uuid4()], owner_id="user_1", question="Anything?"
        )

    assert exc.value.status_code == 404


def test_llm_failure_becomes_a_502():
    from app.integrations.llm.client import LLMUnavailableError

    db, papers, search = _library([("A", "x.", True), ("B", "y.", True)])

    class BrokenLLM:
        def complete(self, *, system, user):
            raise LLMUnavailableError("provider exploded")

    with pytest.raises(HTTPException) as exc:
        _service(db, search, BrokenLLM()).ask(
            [p.id for p in papers], owner_id="user_1", question="Anything?"
        )

    assert exc.value.status_code == 502
    assert "provider exploded" in exc.value.detail
