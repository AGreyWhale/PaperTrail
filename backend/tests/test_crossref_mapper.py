import pytest

from app.integrations.crossref.mapper import CrossRefMappingError, crossref_to_paper_create


def test_maps_a_typical_journal_article():
    data = {
        "title": ["Attention Is All You Need"],
        "author": [
            {"given": "Ashish", "family": "Vaswani"},
            {"given": "Noam", "family": "Shazeer"},
        ],
        "container-title": ["Advances in Neural Information Processing Systems"],
        "published": {"date-parts": [[2017, 6, 12]]},
    }

    paper = crossref_to_paper_create(data)

    assert paper.title == "Attention Is All You Need"
    assert paper.authors == ["Ashish Vaswani", "Noam Shazeer"]
    assert paper.venue == "Advances in Neural Information Processing Systems"
    assert paper.year == 2017


def test_falls_back_to_event_name_when_no_container_title():
    data = {
        "title": ["Some Conference Paper"],
        "author": [{"given": "A", "family": "Author"}],
        "event": {"name": "International Conference on Machine Learning"},
        "issued": {"date-parts": [[2021]]},
    }

    paper = crossref_to_paper_create(data)

    assert paper.venue == "International Conference on Machine Learning"
    assert paper.year == 2021


def test_missing_venue_and_year_become_none():
    data = {
        "title": ["A Paper With Sparse Metadata"],
        "author": [],
    }

    paper = crossref_to_paper_create(data)

    assert paper.venue is None
    assert paper.year is None
    assert paper.authors == []


def test_missing_title_raises():
    data = {"author": [{"given": "A", "family": "Author"}]}

    with pytest.raises(CrossRefMappingError):
        crossref_to_paper_create(data)


def test_author_with_only_family_name_is_used():
    data = {
        "title": ["Group Authorship Example"],
        "author": [{"family": "Consortium"}],
    }

    paper = crossref_to_paper_create(data)

    assert paper.authors == ["Consortium"]
