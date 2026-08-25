import uuid

from fastapi import HTTPException, status

from app.integrations.llm.client import LLMClient, LLMUnavailableError
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import MultiAskAnswerOut, MultiCitationOut
from app.services.multi_paper_retrieval import gather_context
from app.services.search_service import SearchService

#Close to the single-paper prompt in its grounding discipline, but citations
#name the paper as well as the page — with several sources in play, "(p. 4)"
#alone doesn't say which paper it came from.
_SYSTEM_PROMPT = """You answer a researcher's question using several papers at once.

Use ONLY the excerpts provided below. Never draw on outside knowledge of these papers, even if \
you recognise them. If the excerpts don't answer the question, say so plainly.

Cite every claim with the paper's short citation and page, like "(Gao et al., p. 5)". A page \
number alone is not enough here — several papers are in play and the reader needs to know which \
one a claim came from.

Where the papers agree, say so and cite both. Where they disagree or address different aspects, \
make that explicit rather than blending them into one voice.

Use markdown where it aids clarity, including tables to compare papers side by side. If you use a \
table, every cell still needs its page citation — naming the paper in the column header is not a \
substitute, because the reader needs the page to check the claim."""


def build_prompt(question: str, contexts) -> str:
    #Pure function, so prompt shape is testable without an LLM
    blocks = "\n\n".join(c.as_prompt_block() for c in contexts)
    return f"Question: {question}\n\nExcerpts:\n\n{blocks}"


class MultiAskService:
    """Question answering across several papers at once. Separate from the
    single-paper RAG flow, which stays untouched"""

    def __init__(
        self,
        paper_repository: PaperRepository,
        search_service: SearchService,
        llm_client: LLMClient,
    ):
        self.paper_repository = paper_repository
        self.search_service = search_service
        self.llm_client = llm_client

    def ask(
        self, paper_ids: list[uuid.UUID], *, owner_id: str, question: str
    ) -> MultiAskAnswerOut:
        if not question.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Question cannot be empty")

        #The question itself is the retrieval probe, rather than the broad
        #survey probes compare and review use
        contexts = gather_context(
            paper_ids,
            owner_id=owner_id,
            paper_repository=self.paper_repository,
            search_service=self.search_service,
            probes=(question.strip(),),
        )

        if not any(c.excerpts for c in contexts):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "No relevant content found for this question in the selected papers",
            )

        try:
            answer = self.llm_client.complete(
                system=_SYSTEM_PROMPT, user=build_prompt(question, contexts)
            )
        except LLMUnavailableError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"The answer service failed: {exc}"
            ) from exc

        return MultiAskAnswerOut(
            answer=answer,
            #The excerpts actually used, so the UI shows real sources rather
            #than parsing citations back out of the prose
            citations=[
                MultiCitationOut(
                    paper_id=context.paper.id,
                    paper_title=context.paper.title,
                    citation=context.short_citation,
                    page_number=excerpt["page_number"],
                    text=excerpt["text"],
                )
                for context in contexts
                for excerpt in context.excerpts
            ],
        )
