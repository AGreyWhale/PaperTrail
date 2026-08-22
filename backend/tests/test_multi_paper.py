import json
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
from app.services.compare_service import CompareService
from app.services.literature_review_service import LiteratureReviewService
from app.services.search_service import SearchService
from app.workers.embedding_job import run_embedding_job
from tests.fakes import FakeChunkSearch, FakeEmbeddingsClient, FakeJSONLLMClient

_DIMENSIONS = ["datasets", "architecture", "evaluation_metrics", "strengths", "weaknesses", "future_work"]


def _library(specs: list[tuple[str, str, bool]], *, owner_id: str = "user_1"):
    #specs: (title, chunk text, embed?)
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
            run_embedding_job(
                paper.id, owner_id=owner_id, db=db,
                embeddings_client=embeddings_client,
            )
        db.refresh(paper)
        papers.append(paper)

    search_service = SearchService(PaperRepository(db), embeddings_client, FakeChunkSearch(db))
    return db, papers, search_service


def _review_payload(papers, *, omit_cell_for=None) -> str:
    return json.dumps(
        {
            "themes": [
                {
                    "theme": "Evaluation setup",
                    "cells": [
                        {"paper_id": str(p.id), "position": f"{p.title} evaluates on benchmarks."}
                        for p in papers
                        if p.id != omit_cell_for
                    ],
                }
            ],
            "markdown": "## Overview\nBoth papers (Smith et al., p. 4) agree.",
        }
    )


def _compare_payload(papers) -> str:
    return json.dumps(
        {"papers": [{"paper_id": str(p.id), **{d: f"{d} for {p.title}" for d in _DIMENSIONS}} for p in papers]}
    )


def test_compare_returns_one_validated_row_per_paper():
    db, papers, search = _library([("Paper A", "Transformers on ImageNet.", True),
                                   ("Paper B", "Graph networks on Cora.", True)])
    llm = FakeJSONLLMClient(answer=_compare_payload(papers))
    service = CompareService(PaperRepository(db), search, llm)

    result = service.compare([p.id for p in papers], owner_id="user_1")

    assert [r.title for r in result.papers] == ["Paper A", "Paper B"]
    assert result.papers[0].datasets == "datasets for Paper A"
    # Comparison must use the provider's JSON mode, not hope for clean output.
    assert llm.json_mode_used == [True]


def test_compare_rejects_fewer_than_two_papers():
    db, papers, search = _library([("Only One", "Some content.", True)])
    service = CompareService(PaperRepository(db), search, FakeJSONLLMClient())

    with pytest.raises(HTTPException) as exc:
        service.compare([papers[0].id], owner_id="user_1")

    assert exc.value.status_code == 422


def test_compare_rejects_unembedded_papers():
    db, papers, search = _library([("Ready", "Content.", True), ("Not ready", "Content.", False)])
    service = CompareService(PaperRepository(db), search, FakeJSONLLMClient())

    with pytest.raises(HTTPException) as exc:
        service.compare([p.id for p in papers], owner_id="user_1")

    assert exc.value.status_code == 422
    assert "Not ready" in exc.value.detail


def test_compare_refuses_papers_owned_by_someone_else():
    db, papers, search = _library([("Alice A", "Content.", True), ("Alice B", "Content.", True)],
                                  owner_id="user_alice")
    service = CompareService(PaperRepository(db), search, FakeJSONLLMClient())

    # Bob guesses valid ids; ownership is checked server-side regardless.
    with pytest.raises(HTTPException) as exc:
        service.compare([p.id for p in papers], owner_id="user_bob")

    assert exc.value.status_code == 404


def test_compare_rejects_a_forged_id_mixed_in_with_owned_ones():
    db, papers, search = _library([("Mine A", "Content.", True), ("Mine B", "Content.", True)])
    service = CompareService(PaperRepository(db), search, FakeJSONLLMClient())

    with pytest.raises(HTTPException) as exc:
        service.compare([papers[0].id, papers[1].id, uuid.uuid4()], owner_id="user_1")

    assert exc.value.status_code == 404


def test_compare_surfaces_malformed_model_output_as_502():
    db, papers, search = _library([("A", "Content.", True), ("B", "Content.", True)])
    service = CompareService(PaperRepository(db), search, FakeJSONLLMClient(answer="not json at all"))

    with pytest.raises(HTTPException) as exc:
        service.compare([p.id for p in papers], owner_id="user_1")

    assert exc.value.status_code == 502


def test_compare_rejects_a_response_missing_a_paper():
    db, papers, search = _library([("A", "Content.", True), ("B", "Content.", True)])
    partial = json.dumps({"papers": [{"paper_id": str(papers[0].id), **{d: "x" for d in _DIMENSIONS}}]})
    service = CompareService(PaperRepository(db), search, FakeJSONLLMClient(answer=partial))

    # Half a table is worse than a clear failure.
    with pytest.raises(HTTPException) as exc:
        service.compare([p.id for p in papers], owner_id="user_1")

    assert exc.value.status_code == 502


def test_compare_ignores_a_hallucinated_paper_id():
    db, papers, search = _library([("A", "Content.", True), ("B", "Content.", True)])
    payload = json.loads(_compare_payload(papers))
    payload["papers"].append({"paper_id": str(uuid.uuid4()), **{d: "invented" for d in _DIMENSIONS}})
    service = CompareService(PaperRepository(db), search, FakeJSONLLMClient(answer=json.dumps(payload)))

    result = service.compare([p.id for p in papers], owner_id="user_1")

    assert len(result.papers) == 2


def test_literature_review_returns_markdown_and_its_real_sources():
    db, papers, search = _library([("Paper A", "Transformers on ImageNet.", True),
                                   ("Paper B", "Graph networks on Cora.", True)])
    llm = FakeJSONLLMClient(answer=_review_payload(papers))
    service = LiteratureReviewService(PaperRepository(db), search, llm)

    result = service.generate([p.id for p in papers], owner_id="user_1")

    assert result.markdown.startswith("## Overview")
    assert [s.title for s in result.sources] == ["Paper A", "Paper B"]
    assert result.sources[0].citation == "Smith et al."
    # Themes grid: one row, one cell per selected paper.
    assert [t.theme for t in result.themes] == ["Evaluation setup"]
    assert len(result.themes[0].cells) == 2


def test_literature_review_prompt_asks_for_synthesis_not_summary():
    db, papers, search = _library([("A", "Content one.", True), ("B", "Content two.", True)])
    llm = FakeJSONLLMClient(answer=_review_payload(papers))
    service = LiteratureReviewService(PaperRepository(db), search, llm)

    service.generate([p.id for p in papers], owner_id="user_1")

    system = llm.calls[0]["system"]
    assert "nothing else" in system  # grounded
    assert "themes" in system and "## Points of difference" in system
    # Headings must be real markdown, not bold text, or nothing styles them.
    assert "NOT bold text" in system
    # The table covers themes, so the prose must not repeat them as a heading.
    assert "Do NOT include a \"Common themes\" heading" in system
    # Both papers' excerpts actually reached the prompt.
    assert "Content one." in llm.calls[0]["user"]
    assert "Content two." in llm.calls[0]["user"]


def test_literature_review_enforces_the_same_ownership_rule():
    db, papers, search = _library([("Alice A", "Content.", True), ("Alice B", "Content.", True)],
                                  owner_id="user_alice")
    service = LiteratureReviewService(PaperRepository(db), search, FakeJSONLLMClient())

    with pytest.raises(HTTPException) as exc:
        service.generate([p.id for p in papers], owner_id="user_bob")

    assert exc.value.status_code == 404


def test_duplicate_ids_do_not_satisfy_the_two_paper_minimum():
    db, papers, search = _library([("Only One", "Content.", True)])
    service = CompareService(PaperRepository(db), search, FakeJSONLLMClient())

    with pytest.raises(HTTPException) as exc:
        service.compare([papers[0].id, papers[0].id], owner_id="user_1")

    assert exc.value.status_code == 422


def test_review_fills_a_missing_theme_cell_rather_than_failing():
    db, papers, search = _library([("A", "Content one.", True), ("B", "Content two.", True)])
    payload = _review_payload(papers, omit_cell_for=papers[1].id)
    service = LiteratureReviewService(PaperRepository(db), search, FakeJSONLLMClient(answer=payload))

    result = service.generate([p.id for p in papers], owner_id="user_1")

    # A thin grid still helps, unlike a half-built comparison table.
    positions = {c.paper_id: c.position for c in result.themes[0].cells}
    assert positions[papers[1].id] == "Not discussed in the retrieved excerpts"


def test_review_drops_themes_referencing_papers_not_selected():
    db, papers, search = _library([("A", "Content one.", True), ("B", "Content two.", True)])
    payload = json.loads(_review_payload(papers))
    payload["themes"][0]["cells"].append({"paper_id": str(uuid.uuid4()), "position": "invented"})
    service = LiteratureReviewService(
        PaperRepository(db), search, FakeJSONLLMClient(answer=json.dumps(payload))
    )

    result = service.generate([p.id for p in papers], owner_id="user_1")

    assert len(result.themes[0].cells) == 2


def test_review_rejects_an_empty_narrative():
    db, papers, search = _library([("A", "Content one.", True), ("B", "Content two.", True)])
    bad = json.dumps({"themes": [], "markdown": "   "})
    service = LiteratureReviewService(PaperRepository(db), search, FakeJSONLLMClient(answer=bad))

    with pytest.raises(HTTPException) as exc:
        service.generate([p.id for p in papers], owner_id="user_1")

    assert exc.value.status_code == 502
