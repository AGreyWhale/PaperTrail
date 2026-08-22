import io
import re
from dataclasses import dataclass

import pdfplumber

@dataclass
class PageText:
    page_number: int
    text: str

# pdfplumber only inserts a space when the gap between two glyphs exceeds a
# tolerance. Its default is a flat 3 points, which is wider than the real word
# gaps in tightly-kerned journal PDFs — those came out as
# "IEEETRANSACTIONSONPATTERN...". The ratio form scales the tolerance with font
# size instead, so it holds for both body text and large display headings.
_X_TOLERANCE_RATIO = 0.15

# pdfplumber emits "(cid:NNN)" for glyphs whose font has no ToUnicode map —
# common in the maths fonts journals use, so equations arrive full of them.
# The character is unrecoverable, so the marker is dropped rather than kept:
# leaving it in means embedding and quoting literal noise.
_CID_ARTIFACT = re.compile(r"\(cid:\d+\)")

def _clean(text: str) -> str:
    text = _CID_ARTIFACT.sub("", text)
    # Equation layout leaves ragged runs of spaces once the markers go.
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r" +\n", "\n", text)

def extract_pages(pdf_bytes: bytes) -> list[PageText]:
    pages: list[PageText] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for index, page in enumerate(pdf.pages, start = 1):
            text = _clean(page.extract_text(x_tolerance_ratio=_X_TOLERANCE_RATIO) or "")
            pages.append(PageText(page_number=index, text=text))
    return pages
    