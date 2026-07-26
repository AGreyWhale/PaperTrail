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
