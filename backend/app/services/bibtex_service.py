import html
import re
import unicodedata
import uuid

from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bwriter import BibTexWriter
from fastapi import HTTPException, status
from pylatexenc.latexencode import unicode_to_latex

from app.models.paper import Paper
from app.repositories.paper_repository import PaperRepository

#Words that mark a venue as a conference proceeding rather than a journal.
#Deliberately a short keyword list, not real citation-type detection: getting
#this exactly right needs a venue database, and @misc is a safe fallback.
_CONFERENCE_HINTS = (
    "conference", "proceedings", "symposium", "workshop", "congress", "meeting",
    "neurips", "nips", "icml", "iclr", "cvpr", "iccv", "eccv", "acl", "emnlp",
    "naacl", "aaai", "ijcai", "kdd", "sigir", "sigmod", "chi", "uist",
)
_JOURNAL_HINTS = ("journal", "transactions", "letters", "review", "quarterly", "annals")
#Preprint servers aren't peer-reviewed venues, so @misc is more honest
_PREPRINT_HINTS = ("arxiv", "biorxiv", "medrxiv", "preprint", "ssrn")

#Very common title words make a poor citation key
_STOPWORDS = frozenset(
    "a an the of on in for to and or with without via using is are be new".split()
)


def _strip_markup(value: str) -> str:
    #CrossRef titles carry HTML: "z &lt; 3.5" and "<i>z</i>" both show up in
    #real metadata, and escaping them for LaTeX verbatim produces nonsense
    #Tags before entities: unescaping first turns "&lt; <i>" into "< <i>",
    #and the tag pattern then eats from that first bare "<"
    without_tags = re.sub(r"<[^>]+>", "", value)
    return " ".join(html.unescape(without_tags).split())


def _ascii(value: str) -> str:
    #Citation keys must be plain ASCII; accents are folded rather than escaped
    folded = unicodedata.normalize("NFKD", value)
    return "".join(c for c in folded if not unicodedata.combining(c))


def entry_type_for(venue: str | None) -> str:
    """
    @inproceedings for conference-sounding venues, @article for journal-sounding
    ones, @misc when there's no venue to judge by (preprints, manual entries).
    """
    if not venue:
        return "misc"
    #Whole words only: a substring check read "Ma-chi-ne" as the CHI
    #conference and filed IEEE Transactions papers as @inproceedings
    words = set(re.findall(r"[a-z]+", venue.lower()))

    if words & set(_PREPRINT_HINTS):
        return "misc"
    #Journal terms are checked first because they're the more specific signal:
    #"IEEE Transactions on ..." is a journal even when other words look eventy
    if words & set(_JOURNAL_HINTS):
        return "article"
    if words & set(_CONFERENCE_HINTS):
        return "inproceedings"
    #A named venue that matches neither is still a real publication
    return "article"


def citation_key(paper: Paper) -> str:
    """surname + year + first meaningful title word, e.g. vaswani2017attention."""
    first_author = next((a.strip() for a in paper.authors.split(",") if a.strip()), "")
    surname = _ascii(first_author).split()[-1].lower() if first_author else "anon"
    surname = re.sub(r"[^a-z]", "", surname) or "anon"

    year = str(paper.year) if paper.year else "nd"  # n.d. — no date

    #Skips stopwords and fragments like the "D" in "3D Convolutional"
    words = re.findall(r"[A-Za-z]+", _ascii(_strip_markup(paper.title)))
    keyword = next(
        (w.lower() for w in words if len(w) > 2 and w.lower() not in _STOPWORDS), ""
    )

    return f"{surname}{year}{keyword}"


class BibtexService:
    """Formats papers as BibTeX. Pure formatting over fields we already store —
    no LLM, no embeddings, no external lookup"""

    def __init__(self, paper_repository: PaperRepository):
        self.paper_repository = paper_repository

    def for_paper(self, paper_id: uuid.UUID, *, owner_id: str) -> str:
        paper = self.paper_repository.get(paper_id, owner_id=owner_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not Found")
        return self._render([paper])

    def for_papers(self, paper_ids: list[uuid.UUID], *, owner_id: str) -> str:
        unique = list(dict.fromkeys(paper_ids))
        if not unique:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Select at least one paper")

        #Owner-scoped, so ids the client doesn't own simply don't come back
        owned = {p.id: p for p in self.paper_repository.list_by_ids(unique, owner_id=owner_id)}
        if len(owned) != len(unique):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more papers were not found")

        return self._render([owned[pid] for pid in unique])

    @staticmethod
    def _render(papers: list[Paper]) -> str:
        database = BibDatabase()
        database.entries = [_as_entry(paper) for paper in papers]

        writer = BibTexWriter()
        writer.indent = "  "
        #Keep the caller's order rather than re-sorting alphabetically
        writer.order_entries_by = None
        return writer.write(database)


def _as_entry(paper: Paper) -> dict:
    entry_type = entry_type_for(paper.venue)
    entry = {
        "ENTRYTYPE": entry_type,
        "ID": citation_key(paper),
        #BibTeX separates authors with " and "; accents become LaTeX escapes
        "author": unicode_to_latex(
            " and ".join(a.strip() for a in paper.authors.split(",") if a.strip())
        ),
        "title": unicode_to_latex(_strip_markup(paper.title)),
    }
    if paper.year:
        entry["year"] = str(paper.year)
    if paper.venue:
        #booktitle is the conference field; journal is the periodical one
        field = "booktitle" if entry_type == "inproceedings" else "journal"
        entry[field] = unicode_to_latex(_strip_markup(paper.venue))
    return entry
