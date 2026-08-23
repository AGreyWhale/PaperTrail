import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user_id
from app.core.database import Base
from app.main import app
from app.models.paper import Paper
from app.repositories.paper_repository import PaperRepository
from app.services.bibtex_service import BibtexService, citation_key, entry_type_for


def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _paper(db, **kwargs) -> Paper:
    defaults = dict(
        owner_id="user_1", title="Attention Is All You Need",
        authors="Ashish Vaswani, Noam Shazeer", venue="NeurIPS", year=2017,
    )
    paper = Paper(**{**defaults, **kwargs})
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper


@pytest.mark.parametrize(
    "venue,expected",
    [
        ("NeurIPS", "inproceedings"),
        ("Proceedings of the 39th ICML", "inproceedings"),
        ("Nature", "article"),
        ("IEEE Transactions on Pattern Analysis", "article"),
        ("arXiv preprint", "misc"),
        ("bioRxiv", "misc"),
        (None, "misc"),
    ],
)
def test_entry_type_heuristic(venue, expected):
    assert entry_type_for(venue) == expected


def test_citation_key_is_surname_year_keyword():
    db = _db()
    assert citation_key(_paper(db)) == "vaswani2017attention"


def test_citation_key_skips_leading_stopwords():
    db = _db()
    paper = _paper(db, title="On the Measure of Intelligence", authors="Francois Chollet", year=2019)
    # "on" and "the" are skipped in favour of the first meaningful word.
    assert citation_key(paper) == "chollet2019measure"


def test_citation_key_handles_a_missing_year():
    db = _db()
    assert citation_key(_paper(db, year=None)).startswith("vaswanind")


def test_citation_key_folds_accents_to_ascii():
    db = _db()
    paper = _paper(db, authors="Ünal Müller", title="Robust Estimation")
    key = citation_key(paper)
    assert key == "muller2017robust"
    assert key.isascii()


def test_citation_key_survives_an_empty_author_list():
    db = _db()
    assert citation_key(_paper(db, authors="")).startswith("anon")


def test_conference_papers_use_booktitle_not_journal():
    db = _db()
    entry = BibtexService(PaperRepository(db)).for_paper(_paper(db).id, owner_id="user_1")

    assert "@inproceedings{vaswani2017attention" in entry
    assert "booktitle = {NeurIPS}" in entry
    assert "journal" not in entry


def test_journal_papers_use_journal():
    db = _db()
    paper = _paper(db, venue="Nature")
    entry = BibtexService(PaperRepository(db)).for_paper(paper.id, owner_id="user_1")

    assert "@article{" in entry
    assert "journal = {Nature}" in entry


def test_authors_are_separated_the_bibtex_way():
    db = _db()
    entry = BibtexService(PaperRepository(db)).for_paper(_paper(db).id, owner_id="user_1")

    # BibTeX uses " and ", not commas, between authors.
    assert "author = {Ashish Vaswani and Noam Shazeer}" in entry


def test_unicode_is_escaped_for_latex():
    db = _db()
    paper = _paper(db, authors="Ünal Müller", title="Robust Estimation")
    entry = BibtexService(PaperRepository(db)).for_paper(paper.id, owner_id="user_1")

    assert "Ü" not in entry and "ü" not in entry
    assert '\\"U' in entry


def test_bulk_export_returns_one_entry_per_paper_in_order():
    db = _db()
    first = _paper(db, title="First Paper", authors="Ada Lovelace", year=2001)
    second = _paper(db, title="Second Paper", authors="Alan Turing", year=2002)

    output = BibtexService(PaperRepository(db)).for_papers(
        [first.id, second.id], owner_id="user_1"
    )

    assert output.count("@") == 2
    assert output.index("lovelace2001") < output.index("turing2002")


def test_bulk_export_rejects_an_empty_selection():
    db = _db()
    with pytest.raises(HTTPException) as exc:
        BibtexService(PaperRepository(db)).for_papers([], owner_id="user_1")
    assert exc.value.status_code == 422


def test_bulk_export_refuses_ids_the_user_does_not_own():
    db = _db()
    alice = _paper(db, owner_id="user_alice")

    with pytest.raises(HTTPException) as exc:
        BibtexService(PaperRepository(db)).for_papers([alice.id], owner_id="user_bob")

    assert exc.value.status_code == 404


def test_bulk_export_rejects_a_forged_id_mixed_with_owned_ones():
    db = _db()
    mine = _paper(db)
    with pytest.raises(HTTPException) as exc:
        BibtexService(PaperRepository(db)).for_papers([mine.id, uuid.uuid4()], owner_id="user_1")
    assert exc.value.status_code == 404


def test_bibtex_endpoint_serves_a_downloadable_entry(client):
    paper_id = client.post(
        "/api/papers", json={"title": "A Paper", "authors": ["Jane Smith"], "year": 2023}
    ).json()["id"]

    response = client.get(f"/api/papers/{paper_id}/bibtex")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-bibtex")
    assert "smith2023paper" in response.text


def test_bulk_endpoint_sets_a_download_filename(client):
    ids = [
        client.post("/api/papers", json={"title": f"Paper {n}", "authors": ["A B"]}).json()["id"]
        for n in range(2)
    ]

    response = client.post("/api/papers/bibtex-export", json={"paper_ids": ids})

    assert response.status_code == 200
    assert "papertrail.bib" in response.headers["content-disposition"]
    assert response.text.count("@") == 2


def test_bibtex_export_route_is_not_parsed_as_a_paper_id(client):
    # /{paper_id} would swallow this path if it were declared first.
    assert client.post("/api/papers/bibtex-export", json={"paper_ids": []}).status_code == 422


def test_bibtex_endpoint_refuses_another_users_paper(client):
    app.dependency_overrides[get_current_user_id] = lambda: "user_alice"
    paper_id = client.post(
        "/api/papers", json={"title": "Alice's Paper", "authors": ["Alice"]}
    ).json()["id"]

    app.dependency_overrides[get_current_user_id] = lambda: "user_bob"
    assert client.get(f"/api/papers/{paper_id}/bibtex").status_code == 404


# --- regressions found against real CrossRef metadata ---

def test_journal_wins_over_a_substring_that_looks_like_a_conference():
    # "Ma-chi-ne" matched the CHI conference under a substring check, filing
    # IEEE Transactions papers as @inproceedings.
    assert entry_type_for("IEEE Transactions on Pattern Analysis and Machine Intelligence") == "article"


def test_conference_hints_still_match_as_whole_words():
    assert entry_type_for("CHI Conference on Human Factors") == "inproceedings"


def test_html_in_a_crossref_title_is_stripped_not_escaped():
    db = _db()
    paper = _paper(db, title="Galaxies at 1.5 &lt; <i>z</i> &lt; 3.5", venue="Nature")

    entry = BibtexService(PaperRepository(db)).for_paper(paper.id, owner_id="user_1")

    # Neither raw tags nor entity text should survive into the .bib file.
    assert "<i>" not in entry
    assert "&lt;" not in entry
    assert "ensuremath{<}i" not in entry


def test_citation_key_skips_fragments_shorter_than_three_letters():
    db = _db()
    paper = _paper(db, title="3D Convolutional Neural Networks", authors="Shuiwang Ji", year=2013)

    # "D" is a fragment, not a keyword — this used to produce "ji2013d".
    assert citation_key(paper) == "ji2013convolutional"
