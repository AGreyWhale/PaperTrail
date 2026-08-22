import json
import uuid

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.integrations.llm.client import LLMClient, LLMUnavailableError
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import ComparisonOut, ComparisonRowOut
from app.services.multi_paper_retrieval import gather_context
from app.services.search_service import SearchService

_DIMENSIONS = ("datasets", "architecture", "evaluation_metrics", "strengths", "weaknesses", "future_work")

_SYSTEM_PROMPT = """You compare academic papers for a researcher, using ONLY the excerpts provided.
Never state anything the excerpts don't support — if a dimension isn't covered for a paper, \
write exactly "Not discussed in the retrieved excerpts" for that field rather than guessing or \
drawing on outside knowledge of the paper.

Reply with a JSON object of this exact shape and nothing else:

{"papers": [{"paper_id": "<the id given>", "datasets": "...", "architecture": "...", \
"evaluation_metrics": "...", "strengths": "...", "weaknesses": "...", "future_work": "..."}]}

Include one entry per paper, keeping the paper_id exactly as given. Keep each field to one or two \
short sentences — this renders in a comparison table, not prose."""


class CompareService:
    """Structured side-by-side comparison across papers. Returns validated
    rows rather than markdown, so the frontend renders a real table"""

    def __init__(
        self,
        paper_repository: PaperRepository,
        search_service: SearchService,
        llm_client: LLMClient,
    ):
        self.paper_repository = paper_repository
        self.search_service = search_service
        self.llm_client = llm_client

    def compare(self, paper_ids: list[uuid.UUID], *, owner_id: str) -> ComparisonOut:
        contexts = gather_context(
            paper_ids,
            owner_id=owner_id,
            paper_repository=self.paper_repository,
            search_service=self.search_service,
        )

        user_prompt = "\n\n".join(c.as_prompt_block() for c in contexts)
        try:
            raw = self.llm_client.complete(
                system=_SYSTEM_PROMPT, user=user_prompt, json_mode=True
            )
        except LLMUnavailableError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"The comparison service failed: {exc}"
            ) from exc

        return self._parse(raw, contexts)

    @staticmethod
    def _parse(raw: str, contexts) -> ComparisonOut:
        #json_mode guarantees valid JSON, not the right shape, so this still
        #validates and fails loudly rather than returning half-built rows
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "The model returned a malformed comparison"
            ) from exc

        by_id = {str(c.paper.id): c for c in contexts}
        rows = []
        for entry in payload.get("papers", []):
            context = by_id.get(str(entry.get("paper_id", "")))
            if context is None:
                # A hallucinated or mangled id — drop it rather than inventing
                # a row for a paper the user didn't select.
                continue
            try:
                rows.append(
                    ComparisonRowOut(
                        paper_id=context.paper.id,
                        title=context.paper.title,
                        **{d: str(entry.get(d) or "Not discussed in the retrieved excerpts")
                           for d in _DIMENSIONS},
                    )
                )
            except ValidationError as exc:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY, "The model returned an unexpected comparison shape"
                ) from exc

        if len(rows) != len(contexts):
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "The comparison came back incomplete — try again",
            )
        return ComparisonOut(papers=rows)
