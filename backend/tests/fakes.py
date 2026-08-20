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
