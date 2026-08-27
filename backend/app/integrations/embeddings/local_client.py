from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import onnxruntime as ort
    from tokenizers import Tokenizer

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"

_BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

#Longer inputs are truncated rather than rejected; chunks sit well under this
_MAX_TOKENS = 512
#Keeps peak memory flat regardless of how many chunks a paper has
_BATCH_SIZE = 16

#ONNX input name -> the attribute holding it on a tokenizers Encoding
_INPUT_ATTRS = {
    "input_ids": "ids",
    "attention_mask": "attention_mask",
    "token_type_ids": "type_ids",
}


@lru_cache
def _load(model_name: str) -> tuple["ort.InferenceSession", "Tokenizer"]:
    """
    Loads the ONNX export and its tokenizer, cached per process.

    Deliberately not sentence-transformers: that pulls in torch, which took the
    API process to ~950MB RSS and put it over a 512MB host limit. Running the
    same model through onnxruntime lands around 350MB and produces identical
    vectors (cosine 1.0 against sentence-transformers), so previously stored
    embeddings stay valid.

    Imports are inside the function so nothing loads until an embedding is
    actually needed.
    """
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer

    session = ort.InferenceSession(
        hf_hub_download(model_name, "onnx/model.onnx"), providers=["CPUExecutionProvider"]
    )
    tokenizer = Tokenizer.from_pretrained(model_name)
    tokenizer.enable_truncation(max_length=_MAX_TOKENS)
    tokenizer.enable_padding()
    return session, tokenizer


class EmbeddingsClient:
    """Wraps a local ONNX sentence-embedding model. Runs on CPU, needs no API
    key, and never leaves the machine.

    Accepts an optional pre-loaded (session, tokenizer) pair for tests"""

    def __init__(self, *, model_name: str = DEFAULT_MODEL, model: tuple | None = None):
        self._model_name = model_name
        self._model = model

    def _ensure_model(self) -> tuple:
        #Loaded on first real use, not in __init__: every request that builds a
        #service gets one of these, and most never embed anything
        if self._model is None:
            self._model = _load(self._model_name)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            vectors.extend(self._encode(texts[start : start + _BATCH_SIZE]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        #BGE expects the query, not the passages, to carry this prefix
        return self._encode([_BGE_QUERY_INSTRUCTION + text])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        session, tokenizer = self._ensure_model()
        encodings = tokenizer.encode_batch(texts)

        feed = {
            spec.name: np.array(
                [getattr(e, _INPUT_ATTRS[spec.name]) for e in encodings], dtype=np.int64
            )
            for spec in session.get_inputs()
        }
        hidden = session.run(None, feed)[0]

        #BGE pools the CLS token, not the mean. Mean pooling scores ~0.95
        #against the real thing — similar enough to look correct while
        #quietly degrading every retrieval.
        pooled = hidden[:, 0]
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        return (pooled / np.where(norms == 0, 1, norms)).tolist()
