import re
import uuid

from fastapi import HTTPException, status

from app.integrations.embeddings.local_client import EmbeddingsClient
from app.repositories.paper_repository import PaperRepository
from app.vectorstore.client import VectorStore

#How many chunks to pull per requested paper before grouping collapses them
CHUNKS_PER_PAPER = 4

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z0-9]+")
#Too common to say anything about where a match is
_STOPWORDS = frozenset(
    "the a an and or of to in for on with is are was were be been it its this that these those "
    "as at by from we our they their he she you i not can may".split()
)


def query_terms(query: str) -> set[str]:
    return {w for w in _WORD.findall(query.lower()) if len(w) > 2 and w not in _STOPWORDS}


def focus_snippet(text: str, query: str, *, max_chars: int = 320) -> str:
    """
    Narrows a ~500-token chunk to the sentence that actually matched, plus
    enough neighbours to read naturally — the Ctrl-F view rather than the whole
    page. Falls back to the opening sentences when the match was purely
    semantic and shares no words with the query.
    """
    flat = " ".join(text.split())
    sentences = [s for s in _SENTENCE_BOUNDARY.split(flat) if s.strip()]
    if not sentences:
        return flat[:max_chars]

    terms = query_terms(query)
    scores = [len(terms & set(_WORD.findall(s.lower()))) for s in sentences]
    best = max(range(len(sentences)), key=lambda i: scores[i]) if terms else 0
    if scores[best] == 0:
        best = 0

    # Grow outwards from the matched sentence until the budget runs out.
    start = end = best
    length = len(sentences[best])
    while length < max_chars:
        grew = False
        if end + 1 < len(sentences) and length + len(sentences[end + 1]) <= max_chars:
            end += 1
            length += len(sentences[end])
            grew = True
        if start > 0 and length + len(sentences[start - 1]) <= max_chars:
            start -= 1
            length += len(sentences[start])
            grew = True
        if not grew:
            break

    snippet = " ".join(sentences[start : end + 1])
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rsplit(" ", 1)[0]
    return ("… " if start > 0 else "") + snippet + (" …" if end < len(sentences) - 1 else "")


class SearchService:
    """Semantic search over embedded chunks, either inside one paper
    (the reading view) or across the whole library (the search page)"""

    def __init__(
        self,
        paper_repository: PaperRepository,
        embeddings_client: EmbeddingsClient,
        vector_store: VectorStore,
    ):
        self.paper_repository = paper_repository
        self.embeddings_client = embeddings_client
        self.vector_store = vector_store

    def search_within_paper(
        self, paper_id: uuid.UUID, *, owner_id: str, query: str, top_k: int = 5
    ) -> list[dict]:
        paper = self.paper_repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found")
        if paper.embedding_status != "embedded":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "This paper hasn't been embedded yet"
            )

        query_embedding = self.embeddings_client.embed_query(query)
        return self.vector_store.query_within_paper(
            owner_id=owner_id, paper_id=paper.id, query_embedding=query_embedding, top_k=top_k
        )

    def search_library(self, *, owner_id: str, query: str, limit: int = 10) -> list[dict]:
        #One result per paper, not per chunk. Three matching chunks from the
        #same paper is one hit showing its strongest excerpt, not three rows.
        #Over-fetches chunks because grouping collapses them
        if not query.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Query cannot be empty")

        query_embedding = self.embeddings_client.embed_query(query)
        matches = self.vector_store.query_for_owner(
            owner_id=owner_id, query_embedding=query_embedding, top_k=limit * CHUNKS_PER_PAPER
        )
        if not matches:
            return []

        best: dict[uuid.UUID, dict] = {}
        for match in matches:
            paper_id = match["paper_id"]
            existing = best.get(paper_id)
            if existing is None:
                best[paper_id] = {"match": match, "count": 1}
            else:
                existing["count"] += 1
                if match["score"] > existing["match"]["score"]:
                    existing["match"] = match

        papers = {
            p.id: p
            for p in self.paper_repository.list_by_ids(list(best), owner_id=owner_id)
        }

        results = [
            {
                "paper_id": paper_id,
                "title": papers[paper_id].title,
                "authors": [a.strip() for a in papers[paper_id].authors.split(",") if a.strip()],
                "venue": papers[paper_id].venue,
                "year": papers[paper_id].year,
                "excerpt": focus_snippet(group["match"]["text"], query),
                "page_number": group["match"]["page_number"],
                "score": group["match"]["score"],
                "match_count": group["count"],
            }
            # A paper deleted since it was embedded still has vectors, so skip
            # anything the DB no longer knows about rather than KeyError-ing.
            for paper_id, group in best.items()
            if paper_id in papers
        ]
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]
