"""
The one place the real pgvector SQL is exercised.

Everything else in this suite runs on in-memory SQLite with no external
services, and that property is worth protecting. SQLite stores and returns a
Vector column fine, but cosine_distance() is a Postgres extension function, so
the similarity queries in ChunkRepository cannot run there. Rather than mock
the distance computation and pretend, these tests skip by default and run
against a real Postgres when TEST_DATABASE_URL is set (see pytest.ini).
"""
import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.chunk import Chunk
from app.models.paper import Paper
from app.repositories.chunk_repository import ChunkRepository

pytestmark = pytest.mark.pg

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    pytest.skip("set TEST_DATABASE_URL to run pgvector tests", allow_module_level=True)


def _vec(*head: float) -> list[float]:
    #384 dims to match the column, only the head carries signal
    return list(head) + [0.0] * (384 - len(head))


@pytest.fixture()
def db():
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _paper(db, owner_id: str, title: str = "A Paper") -> Paper:
    paper = Paper(owner_id=owner_id, title=title, authors="A. Author")
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper


def _chunk(db, paper: Paper, text_value: str, page: int = 1) -> Chunk:
    chunk = Chunk(
        paper_id=paper.id, chunk_index=0, page_number=page, text=text_value, token_count=10
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


def test_embeddings_round_trip_through_the_column(db):
    paper = _paper(db, "user_1")
    chunk = _chunk(db, paper, "Some content.")
    repo = ChunkRepository(db)

    repo.store_embeddings([(chunk.id, _vec(1.0, 0.0))])

    db.refresh(chunk)
    assert list(chunk.embedding)[:2] == [1.0, 0.0]


def test_similarity_ranks_the_nearest_chunk_first(db):
    paper = _paper(db, "user_1")
    near = _chunk(db, paper, "Nearly identical.", page=1)
    far = _chunk(db, paper, "Quite different.", page=2)
    repo = ChunkRepository(db)
    repo.store_embeddings([(near.id, _vec(1.0, 0.0)), (far.id, _vec(0.0, 1.0))])

    results = repo.find_similar_within_paper(
        paper.id, owner_id="user_1", query_embedding=_vec(1.0, 0.0), top_k=2
    )

    assert [r["text"] for r in results] == ["Nearly identical.", "Quite different."]
    assert results[0]["score"] > 0.99


def test_unembedded_chunks_are_excluded(db):
    paper = _paper(db, "user_1")
    embedded = _chunk(db, paper, "Embedded.", page=1)
    _chunk(db, paper, "Never embedded.", page=2)
    repo = ChunkRepository(db)
    repo.store_embeddings([(embedded.id, _vec(1.0))])

    results = repo.find_similar_within_paper(
        paper.id, owner_id="user_1", query_embedding=_vec(1.0), top_k=10
    )

    # A NULL embedding must not sort to the top as a zero distance.
    assert [r["text"] for r in results] == ["Embedded."]


def test_within_paper_query_refuses_another_owners_paper(db):
    alice = _paper(db, "user_alice", "Alice's Paper")
    chunk = _chunk(db, alice, "Alice's content.")
    repo = ChunkRepository(db)
    repo.store_embeddings([(chunk.id, _vec(1.0))])

    # Defence in depth: callers check ownership first, but the SQL itself must
    # make a cross-owner result impossible.
    assert (
        repo.find_similar_within_paper(
            alice.id, owner_id="user_bob", query_embedding=_vec(1.0), top_k=10
        )
        == []
    )


def test_within_paper_query_does_not_leak_other_papers(db):
    paper_a = _paper(db, "user_1", "Paper A")
    paper_b = _paper(db, "user_1", "Paper B")
    a_chunk = _chunk(db, paper_a, "From A.")
    b_chunk = _chunk(db, paper_b, "From B.")
    repo = ChunkRepository(db)
    repo.store_embeddings([(a_chunk.id, _vec(1.0)), (b_chunk.id, _vec(1.0))])

    results = repo.find_similar_within_paper(
        paper_a.id, owner_id="user_1", query_embedding=_vec(1.0), top_k=10
    )

    assert [r["text"] for r in results] == ["From A."]


def test_owner_wide_query_spans_papers_and_carries_paper_id(db):
    paper_a = _paper(db, "user_1", "Paper A")
    paper_b = _paper(db, "user_1", "Paper B")
    a_chunk = _chunk(db, paper_a, "From A.")
    b_chunk = _chunk(db, paper_b, "From B.")
    repo = ChunkRepository(db)
    repo.store_embeddings([(a_chunk.id, _vec(1.0, 0.0)), (b_chunk.id, _vec(0.9, 0.1))])

    results = repo.find_similar_for_owner(
        owner_id="user_1", query_embedding=_vec(1.0, 0.0), top_k=10
    )

    assert {r["paper_id"] for r in results} == {paper_a.id, paper_b.id}


def test_owner_wide_query_never_crosses_owners(db):
    alice = _paper(db, "user_alice")
    chunk = _chunk(db, alice, "Alice's content.")
    ChunkRepository(db).store_embeddings([(chunk.id, _vec(1.0))])

    assert (
        ChunkRepository(db).find_similar_for_owner(
            owner_id="user_bob", query_embedding=_vec(1.0), top_k=10
        )
        == []
    )


def test_deleting_a_paper_takes_its_embeddings(db):
    paper = _paper(db, "user_1")
    chunk = _chunk(db, paper, "Content.")
    ChunkRepository(db).store_embeddings([(chunk.id, _vec(1.0))])

    chunk_id = chunk.id
    db.delete(paper)
    db.commit()
    # The cascade happens in the database, so the session's identity map still
    # holds the now-deleted Chunk. Drop it before asking.
    db.expunge_all()

    # Cascade, not a separate cleanup step — this is what let delete_for_paper go.
    assert db.query(Chunk).filter(Chunk.id == chunk_id).count() == 0
