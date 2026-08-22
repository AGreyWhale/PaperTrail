from app.parsing.pdf_parser import extract_pages
from tests.pdf_helpers import make_test_pdf


def test_extracts_text_from_each_page():
    pdf_bytes = make_test_pdf(["First page content.", "Second page content."])

    pages = extract_pages(pdf_bytes)

    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert "First page content" in pages[0].text
    assert pages[1].page_number == 2
    assert "Second page content" in pages[1].text


def test_single_page_pdf():
    pdf_bytes = make_test_pdf(["Only page."])

    pages = extract_pages(pdf_bytes)

    assert len(pages) == 1
    assert pages[0].page_number == 1


def test_cid_artifacts_are_stripped_from_extracted_text():
    from app.parsing.pdf_parser import _clean

    # What a maths-heavy line looks like before cleaning.
    raw = "X (cid:96)+1 = σ(Dˆ− 1 2  Aˆ X (cid:96) W (cid:96) ), (1)"

    cleaned = _clean(raw)

    assert "cid:" not in cleaned
    assert "  " not in cleaned
    # The actual maths survives — only the unrecoverable markers go.
    assert "σ" in cleaned and "(1)" in cleaned
