class FakeLLMClient:
    """Records the prompts it was called with and returns a canned answer,
    so tests can assert what context RagService built without an API call"""

    def __init__(self, answer: str = "This is the answer. (p. 1)"):
        self.answer = answer
        self.calls: list[dict] = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        return self.answer


class FakeEmbeddingsClient:
    """Same text always produces the same vector, so round-trip retrieval
    tests can assert exact matches.

    Unlike the real client, embed_query() skips the BGE instruction
    prefix on purpose. These tests prove the embed -> store -> retrieve
    plumbing works, and the prefix would stop "query a stored chunk's
    exact text" from matching"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    @staticmethod
    def _embed_one(text: str) -> list[float]:
        vec = [0.0] * 8
        for i, ch in enumerate(text):
            vec[i % 8] += ord(ch)
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]


class FakeJSONLLMClient(FakeLLMClient):
    """Returns a canned JSON payload and records whether json_mode was asked
    for, so compare-mode tests can assert the provider contract too."""

    def __init__(self, answer: str = "{}"):
        super().__init__(answer)
        self.json_mode_used: list[bool] = []

    def complete(self, *, system: str, user: str, json_mode: bool = False) -> str:
        self.json_mode_used.append(json_mode)
        return super().complete(system=system, user=user)


class FakeChunkSearch:
    """
    Stands in for ChunkRepository's similarity queries, which are pgvector SQL
    and therefore Postgres-only — the rest of the suite runs on SQLite with no
    external services, and that property is worth keeping.

    Storage still goes through the real repository (Vector columns round-trip
    fine on SQLite); only the cosine ranking is computed here in Python. The
    real SQL is covered separately in test_pgvector.py against a real Postgres.
    """

    def __init__(self, db):
        from app.repositories.chunk_repository import ChunkRepository

        self._real = ChunkRepository(db)
        self.db = db

    def __getattr__(self, name):
        # Everything that isn't a similarity query is the real repository.
        return getattr(self._real, name)

    def find_similar_within_paper(self, paper_id, *, owner_id, query_embedding, top_k=5):
        return self._rank(query_embedding, top_k, owner_id=owner_id, paper_id=paper_id)

    def find_similar_for_owner(self, *, owner_id, query_embedding, top_k=20, paper_ids=None):
        return self._rank(
            query_embedding, top_k, owner_id=owner_id, with_paper_id=True, scope=paper_ids
        )

    def _rank(
        self, query_embedding, top_k, *, owner_id, paper_id=None, with_paper_id=False, scope=None
    ):
        from app.models.chunk import Chunk
        from app.models.paper import Paper

        rows = (
            self.db.query(Chunk, Paper)
            .join(Paper, Paper.id == Chunk.paper_id)
            # Same owner scoping the real query enforces in SQL.
            .filter(Paper.owner_id == owner_id)
            .all()
        )
        matches = []
        for chunk, _paper in rows:
            if chunk.embedding is None:
                continue
            if paper_id is not None and chunk.paper_id != paper_id:
                continue
            # Mirrors the real query's paper_ids restriction.
            if scope is not None and chunk.paper_id not in scope:
                continue
            match = {
                "chunk_id": chunk.id,
                "text": chunk.text,
                "page_number": chunk.page_number,
                "score": _cosine(list(chunk.embedding), query_embedding),
            }
            if with_paper_id:
                match["paper_id"] = chunk.paper_id
            matches.append(match)

        matches.sort(key=lambda m: m["score"], reverse=True)
        return matches[:top_k]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = (sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5)
    return dot / norm if norm else 0.0
