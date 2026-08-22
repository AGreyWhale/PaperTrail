import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.chunk import Chunk
from app.models.paper import Paper
from app.repositories.paper_repository import PaperRepository
from app.services.search_service import SearchService
from app.workers.embedding_job import run_embedding_job
from tests.fakes import FakeChunkSearch, FakeEmbeddingsClient


def _library(papers: dict[str, list[str]], *, owner_id: str = "user_1"):
    #papers maps title -> chunk texts, all embedded into one shared store
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    embeddings_client = FakeEmbeddingsClient()

    for title, texts in papers.items():
        paper = Paper(
            owner_id=owner_id, title=title, authors="A. Author", processing_status="processed"
        )
        db.add(paper)
        db.commit()
        db.refresh(paper)
        for i, text in enumerate(texts):
            db.add(
                Chunk(
                    paper_id=paper.id, chunk_index=i, page_number=i + 1, text=text, token_count=10
                )
            )
        db.commit()
        run_embedding_job(
            paper.id,
            owner_id=owner_id,
            db=db,
            embeddings_client=embeddings_client,
        )

    service = SearchService(PaperRepository(db), embeddings_client, FakeChunkSearch(db))
    return db, service


def test_search_spans_every_paper_in_the_library():
    _, service = _library(
        {
            "Transformers Paper": ["Attention mechanisms are explained here."],
            "Diffusion Paper": ["Denoising diffusion probabilistic models."],
        }
    )

    results = service.search_library(owner_id="user_1", query="Attention mechanisms are explained here.")

    assert len(results) == 2
    # Best match first, and it reaches a paper the query didn't name.
    assert results[0]["title"] == "Transformers Paper"


def test_multiple_matching_chunks_collapse_to_one_result_per_paper():
    _, service = _library(
        {
            "Transformers Paper": [
                "Attention mechanisms are explained here.",
                "Attention mechanisms are explained here too.",
                "Attention mechanisms appear again here.",
            ]
        }
    )

    results = service.search_library(owner_id="user_1", query="Attention mechanisms are explained here.")

    assert len(results) == 1
    assert results[0]["match_count"] == 3
    # The excerpt shown is the strongest chunk, not just the first one.
    assert results[0]["excerpt"] == "Attention mechanisms are explained here."
    assert results[0]["page_number"] == 1


def test_search_never_crosses_owners():
    db, service = _library({"Alice's Paper": ["Alice's private content."]}, owner_id="user_alice")

    assert service.search_library(owner_id="user_bob", query="Alice's private content.") == []


def test_search_rejects_an_empty_query():
    _, service = _library({"A Paper": ["Some content."]})

    with pytest.raises(HTTPException) as exc_info:
        service.search_library(owner_id="user_1", query="   ")

    assert exc_info.value.status_code == 422


def test_search_returns_nothing_for_an_empty_library():
    _, service = _library({})

    assert service.search_library(owner_id="user_1", query="anything at all") == []


def test_search_skips_papers_deleted_since_embedding():
    db, service = _library({"Doomed Paper": ["Content that will be orphaned."]})
    db.query(Paper).delete()
    db.commit()

    # Vectors outlive the row; the result should be dropped, not KeyError.
    assert service.search_library(owner_id="user_1", query="Content that will be orphaned.") == []
