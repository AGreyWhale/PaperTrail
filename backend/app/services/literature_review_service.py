import json
import uuid

from fastapi import HTTPException, status

from app.integrations.llm.client import LLMClient, LLMUnavailableError
from app.repositories.paper_repository import PaperRepository
from app.schemas.paper import (
    LiteratureReviewOut,
    ReviewSourceOut,
    ThemeCellOut,
    ThemeOut,
)
from app.services.multi_paper_retrieval import gather_context
from app.services.search_service import SearchService

#Deliberately not the /ask prompt: that one answers a question from one paper.
#This one has to synthesise ACROSS papers, so it asks for themes, agreement and
#disagreement, and gaps — and cites by paper, not just page.
NOT_DISCUSSED = "Not discussed in the retrieved excerpts"

#Deliberately not the /ask prompt: that one answers a question from one paper.
#This one synthesises ACROSS papers, and returns two things — a themes grid the
#reader can scan, and the narrative that explains it.
_SYSTEM_PROMPT = """You write a literature review synthesising several papers for a researcher.

Ground everything in the excerpts provided and nothing else. Where the excerpts don\'t cover \
something, say so rather than filling the gap from outside knowledge.

Reply with a JSON object of exactly this shape and nothing else:

{"themes": [{"theme": "<short label, 2-5 words>", "cells": [{"paper_id": "<id as given>", \
"position": "<one sentence on what THIS paper says about this theme>"}]}], "markdown": "<the review>"}

For "themes": identify 3 to 5 recurring themes the papers genuinely share or disagree on. Give \
every selected paper a cell in every theme — if a paper doesn\'t address it, set position to \
exactly "Not discussed in the retrieved excerpts". Keep each position to one short sentence: \
this renders in a table, not prose.

For "markdown": the narrative synthesis. Use markdown H2 headings written exactly like this,
with the ## characters — NOT bold text, which does not render as a heading:

## Overview
what these papers collectively address

## Points of difference
where methods, data or conclusions diverge, and how

## Gaps and open questions
what the excerpts suggest is unresolved

Do NOT include a "Common themes" heading in the markdown — the themes table already covers it, \
so the prose should explain and connect rather than repeat it.

Cite by paper, not just page: use the short citation from each paper\'s heading with the page, \
like "(Vaswani et al., p. 4)". Compare and contrast actively — a review that summarises each \
paper in turn has failed."""



class LiteratureReviewService:
    """Long-form synthesis across papers, cited by paper rather than by page
    alone since the point is connecting sources to each other"""

    def __init__(
        self,
        paper_repository: PaperRepository,
        search_service: SearchService,
        llm_client: LLMClient,
    ):
        self.paper_repository = paper_repository
        self.search_service = search_service
        self.llm_client = llm_client

    def generate(self, paper_ids: list[uuid.UUID], *, owner_id: str) -> LiteratureReviewOut:
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
                status.HTTP_502_BAD_GATEWAY, f"The review service failed: {exc}"
            ) from exc

        payload = self._parse(raw)

        return LiteratureReviewOut(
            themes=self._themes(payload, contexts),
            markdown=str(payload.get("markdown") or "").strip(),
            # Returned so the frontend can show what was actually synthesised,
            # rather than trusting citations parsed out of the prose.
            sources=[
                ReviewSourceOut(
                    paper_id=c.paper.id, title=c.paper.title, citation=c.short_citation
                )
                for c in contexts
            ],
        )

    @staticmethod
    def _parse(raw: str) -> dict:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "The model returned a malformed review"
            ) from exc
        if not isinstance(payload, dict) or not str(payload.get("markdown") or "").strip():
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "The review came back empty — try again"
            )
        return payload

    @staticmethod
    def _themes(payload: dict, contexts) -> list[ThemeOut]:
        #Unlike the compare table, a thin themes grid is still useful, so a
        #missing cell is filled with the sentinel rather than failing the whole
        #request. Ids the user didn't select are dropped either way.
        by_id = {str(c.paper.id): c for c in contexts}
        themes = []
        for entry in payload.get("themes", []):
            label = str(entry.get("theme") or "").strip()
            if not label:
                continue
            stated = {
                str(cell.get("paper_id")): str(cell.get("position") or "").strip()
                for cell in entry.get("cells", [])
                if str(cell.get("paper_id")) in by_id
            }
            themes.append(
                ThemeOut(
                    theme=label,
                    cells=[
                        ThemeCellOut(
                            paper_id=context.paper.id,
                            position=stated.get(pid) or NOT_DISCUSSED,
                        )
                        for pid, context in by_id.items()
                    ],
                )
            )
        return themes
