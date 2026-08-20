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
        self._model = model or _load_model(model_name)
    
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        embedding = self._model.encode(_BGE_QUERY_INSTRUCTION + text, normalize_embeddings=True)
        return embedding.tolist()