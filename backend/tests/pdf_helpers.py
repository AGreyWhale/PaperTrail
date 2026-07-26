from fpdf import FPDF


def make_test_pdf(pages_text: list[str]) -> bytes:
    """Builds a real, valid multi-page PDF from plain text — one page per string."""
    pdf = FPDF()
    for text in pages_text:
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 10, text)
    return bytes(pdf.output())
