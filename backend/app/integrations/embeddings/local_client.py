from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"

_BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

@lru_cache
def _load_model(model_name: str) -> "SentenceTransformer":
    """
    Loads/caches a sentence-transformers model.
    import is in the function on purpose sicne it's a heavy dependency.
    This way, it only loads it when it needs it.
    """
    from sentence_transformers import SentenceTransformer
    
    return SentenceTransformer(model_name)

class EmbeddingsClient:
    """Wraps a local sentence-transformers model
    Accepts optional pre-loaded model for tests"""

    def __init__(self, *, model_name: str = DEFAULT_MODEL, model: "SentenceTransformer | None" = None):
        self._model_name = model_name
        self._model = model

    def _ensure_model(self) -> "SentenceTransformer":
        #Loaded on first real use, not in __init__. FastAPI builds this
        #dependency for every /similar and /ask request including the ones
        #that 401 or 422, and none of those should pull torch into the API
        #process. _load_model is cached, so this costs nothing after the first
        if self._model is None:
            self._model = _load_model(self._model_name)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._ensure_model().encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        embedding = self._ensure_model().encode(
            _BGE_QUERY_INSTRUCTION + text, normalize_embeddings=True
        )
        return embedding.tolist()