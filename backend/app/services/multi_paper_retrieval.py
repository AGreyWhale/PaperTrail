import uuid

from fastapi import HTTPException, status

from app.models.paper import Paper
from app.repositories.paper_repository import PaperRepository
from app.services.search_service import SearchService

MIN_PAPERS = 2
MAX_PAPERS = 6
#Probes chosen to surface the dimensions both features care about, rather than
#dumping whole papers into the prompt
_PROBES = (
    "problem statement, motivation and contributions",
    "method, model architecture and approach",
    "datasets, experiments, evaluation metrics and results",
    "limitations, weaknesses and future work",
)
_CHUNKS_PER_PROBE = 2
_MAX_CHARS_PER_PAPER = 4000


class PaperContext:
    """One paper's retrieved excerpts, ready to drop into a prompt"""

    def __init__(self, paper: Paper, excerpts: list[dict]):
        self.paper = paper
        self.excerpts = excerpts

    @property
    def short_citation(self) -> str:
        #"Smith et al." style, falling back to the title when authors are absent
        first = next((a.strip() for a in self.paper.authors.split(",") if a.strip()), "")
        if not first:
            return self.paper.title[:40]
        surname = first.split()[-1]
        return f"{surname} et al." if "," in self.paper.authors else surname

    def as_prompt_block(self) -> str:
        lines = [f"### {self.short_citation} — \"{self.paper.title}\" (paper_id: {self.paper.id})"]
        for excerpt in self.excerpts:
            lines.append(f"[p. {excerpt['page_number']}] {excerpt['text']}")
        return "\n".join(lines)


def gather_context(
    paper_ids: list[uuid.UUID],
    *,
    owner_id: str,
    paper_repository: PaperRepository,
    search_service: SearchService,
    probes: tuple[str, ...] = _PROBES,
) -> list[PaperContext]:
    """
    Validates a client-supplied list of paper ids and gathers a bounded set of
    excerpts from each. Shared by compare, literature review and multi-paper ask
    so the ownership and readiness rules can't drift apart between them.

    `probes` are the queries used to pull excerpts: the default set covers a
    paper broadly, while ask passes the user's actual question instead.
    """
    unique = list(dict.fromkeys(paper_ids))
    if len(unique) < MIN_PAPERS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Select at least {MIN_PAPERS} papers to compare",
        )
    if len(unique) > MAX_PAPERS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Select at most {MAX_PAPERS} papers — more than that overruns the model's context",
        )

    # Never trust the ids from the client: list_by_ids is owner-scoped, so
    # anything belonging to someone else simply doesn't come back.
    owned = {p.id: p for p in paper_repository.list_by_ids(unique, owner_id=owner_id)}
    missing = [pid for pid in unique if pid not in owned]
    if missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more papers were not found")

    unembedded = [p.title for p in owned.values() if p.embedding_status != "embedded"]
    if unembedded:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"These papers aren't embedded yet: {', '.join(unembedded)}",
        )

    return [
        PaperContext(owned[pid], _excerpts_for(owned[pid], owner_id, search_service, probes))
        for pid in unique
    ]


def _excerpts_for(
    paper: Paper, owner_id: str, search_service: SearchService, probes: tuple[str, ...]
) -> list[dict]:
    #A few targeted probes rather than the whole paper. Multiplying a full
    #paper by six selections is what blows past Groq's per-minute token limit
    seen: set[uuid.UUID] = set()
    excerpts: list[dict] = []
    budget = _MAX_CHARS_PER_PAPER

    #Fewer probes means each one can afford more chunks
    per_probe = max(_CHUNKS_PER_PROBE, 8 // max(len(probes), 1))

    for probe in probes:
        for hit in search_service.search_within_paper(
            paper.id, owner_id=owner_id, query=probe, top_k=per_probe
        ):
            if hit["chunk_id"] in seen:
                continue
            text = hit["text"]
            if len(text) > budget:
                continue
            seen.add(hit["chunk_id"])
            budget -= len(text)
            excerpts.append(hit)

    excerpts.sort(key=lambda e: e["page_number"])
    return excerpts
