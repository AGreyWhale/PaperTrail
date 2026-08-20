import chromadb
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.chunk import Chunk
from app.models.paper import Paper
from app.vectorstore.client import VectorStore
from app.workers.embedding_job import run_embedding_job
from tests.fakes import FakeEmbeddingsClient


def _make_db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _make_paper_with_chunks(db, *, owner_id: str, chunk_texts: list[str]) -> Paper:
    paper = Paper(
        owner_id=owner_id,
        title="Test Paper",
        authors="A. Author",
        processing_status="processed",
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    for i, text in enumerate(chunk_texts):
        db.add(Chunk(paper_id=paper.id, chunk_index=i, page_number=1, text=text, token_count=10))
    db.commit()
    return paper


def test_run_embedding_job_marks_paper_embedded():
    db = _make_db_session()
    paper = _make_paper_with_chunks(
        db, owner_id="user_1", chunk_texts=["First chunk.", "Second chunk."]
    )

    run_embedding_job(
        paper.id,
        owner_id="user_1",
        db=db,
        embeddings_client=FakeEmbeddingsClient(),
        vector_store=VectorStore(chromadb.EphemeralClient()),
    )

    db.refresh(paper)
    assert paper.embedding_status == "embedded"


def test_run_embedding_job_stores_retrievable_vectors():
    db = _make_db_session()
    paper = _make_paper_with_chunks(
        db,
        owner_id="user_1",
        chunk_texts=["Attention mechanisms explained here.", "A completely different topic."],
    )
    vector_store = VectorStore(chromadb.EphemeralClient())
    embeddings_client = FakeEmbeddingsClient()

    run_embedding_job(
        paper.id,
        owner_id="user_1",
        db=db,
        embeddings_client=embeddings_client,
        vector_store=vector_store,
    )

    # Querying a chunk's exact text with the deterministic fake embedder
    # should return that chunk with a near-perfect score.
    query_embedding = embeddings_client.embed_query("Attention mechanisms explained here.")
    results = vector_store.query_within_paper(
        owner_id="user_1", paper_id=paper.id, query_embedding=query_embedding, top_k=1
    )

    assert len(results) == 1
    assert results[0]["text"] == "Attention mechanisms explained here."
    assert results[0]["score"] > 0.999


def test_run_embedding_job_sets_failed_status_on_error():
    db = _make_db_session()
    paper = _make_paper_with_chunks(db, owner_id="user_1", chunk_texts=["Some content."])

    class BrokenEmbeddingsClient:
        def embed_documents(self, texts):
            raise RuntimeError("simulated model failure")

    try:
        run_embedding_job(
            paper.id,
            owner_id="user_1",
            db=db,
            embeddings_client=BrokenEmbeddingsClient(),
            vector_store=VectorStore(chromadb.EphemeralClient()),
        )
    except RuntimeError:
        pass

    db.refresh(paper)
    assert paper.embedding_status == "failed"


def test_run_embedding_job_scopes_vectors_by_owner():
    db = _make_db_session()
    paper = _make_paper_with_chunks(db, owner_id="user_alice", chunk_texts=["Alice's content."])
    vector_store = VectorStore(chromadb.EphemeralClient())
    embeddings_client = FakeEmbeddingsClient()

    run_embedding_job(
        paper.id,
        owner_id="user_alice",
        db=db,
        embeddings_client=embeddings_client,
        vector_store=vector_store,
    )

    # Same paper_id, different owner, should find nothing.
    query_embedding = embeddings_client.embed_query("Alice's content.")
    results = vector_store.query_within_paper(
        owner_id="user_bob", paper_id=paper.id, query_embedding=query_embedding, top_k=5
    )
    assert results == []
