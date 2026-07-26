import io
from dataclasses import dataclass

import pdfplumber

@dataclass
class PageText:
    page_number: int
    text: str

def extract_pages(pdf_bytes: bytes) -> list[PageText]:
    pages: list[PageText] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for index, page in enumerate(pdf.pages, start = 1):
            text = page.extract_text() or ""
            pages.append(PageText(page_number=index, text=text))
    return pages
    