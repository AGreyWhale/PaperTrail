import uuid
from collections.abc import Iterator

from fastapi import HTTPException, status

from app.integrations.llm.client import LLMClient, LLMUnavailableError
from app.services.search_service import SearchService

_SYSTEM_PROMPT = """You are a research assistant helping someone understand an academic paper.
Answer the question using ONLY the excerpts provided below — never rely on outside knowledge, \
even if you're confident about it. Every claim must be followed by a page citation in the \
form (p. N), matching the excerpt it came from. If the excerpts don't contain enough \
information to answer, say so plainly rather than guessing. Use markdown formatting \
(headings, bullet lists) where it aids clarity, but keep the answer focused."""


def build_rag_prompt(question: str, chunks: list[dict]) -> str:
    #Pure function so prompt shape is testable without an LLM or a vector store
    excerpt_blocks = "\n\n".join(
        f"[Excerpt {i + 1}, page {c['page_number']}]\n{c['text']}" for i, c in enumerate(chunks)
    )
    return f"Question: {question}\n\nExcerpts:\n\n{excerpt_blocks}"


class RagService:
    """Retrieve relevant chunks, build a grounded prompt, ask the LLM.
    Returns the chunks it actually used alongside the answer, so the
    frontend shows real sources instead of parsing citations back out"""

    def __init__(self, search_service: SearchService, llm_client: LLMClient):
        self.search_service = search_service
        self.llm_client = llm_client

    def retrieve_context(
        self, paper_id: uuid.UUID, *, owner_id: str, question: str, top_k: int = 5
    ) -> list[dict]:
        #Validation + retrieval, shared by the buffered and streaming paths.
        #Streaming has to do all of this up front: once the first byte is out,
        #the status code is already committed and a 404 can't be sent
        if not question.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Question cannot be empty")

        # search_within_paper already raises 404 / 422 for missing and
        # not-yet-embedded papers, so those checks aren't repeated here.
        chunks = self.search_service.search_within_paper(
            paper_id, owner_id=owner_id, query=question, top_k=top_k
        )
        if not chunks:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "No relevant content found for this question in the paper",
            )
        return chunks

    def stream_answer(self, question: str, chunks: list[dict]) -> Iterator[str]:
        return self.llm_client.stream_complete(
            system=_SYSTEM_PROMPT, user=build_rag_prompt(question, chunks)
        )

    def answer_question(
        self, paper_id: uuid.UUID, *, owner_id: str, question: str, top_k: int = 5
    ) -> dict:
        chunks = self.retrieve_context(
            paper_id, owner_id=owner_id, question=question, top_k=top_k
        )

        try:
            answer = self.llm_client.complete(
                system=_SYSTEM_PROMPT, user=build_rag_prompt(question, chunks)
            )
        except LLMUnavailableError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"The answer service failed: {exc}"
            ) from exc

        return {
            "answer": answer,
            "citations": [
                {"chunk_id": c["chunk_id"], "page_number": c["page_number"], "text": c["text"]}
                for c in chunks
            ],
        }
