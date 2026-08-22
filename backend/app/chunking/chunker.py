import re
from dataclasses import dataclass
from app.parsing.pdf_parser import PageText

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")

# Data tables extract as column-scrambled number soup ("0 0 . . 1 2 7 40.14"),
# which is meaningless as text but still gets embedded and shown as a search
# excerpt. Measured across real papers, prose sits at 0.46-0.72 and table dumps
# at 0.00-0.35, so this threshold separates them with room to spare.
_MIN_PROSE_RATIO = 0.35

def prose_ratio(text: str) -> float:
    #Share of tokens that look like actual words rather than table cells
    tokens = text.split()
    if not tokens:
        return 0.0
    words = [t for t in tokens if len(t) >= 3 and sum(c.isalpha() for c in t) >= len(t) * 0.7]
    return len(words) / len(tokens)

@dataclass
class ChunkResult:
    chunk_index: int
    page_number: int
    text: str
    token_count: int

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

def _sentences_with_pages(pages: list[PageText]) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for page in pages:
        text = page.text.strip()
        if not text:
            continue
        for sentence in _SENTENCE_BOUNDARY.split(text):
            sentence = sentence.strip()
            if sentence:
                result.append((sentence, page.page_number))
    return result

def chunk_pages(
    pages: list[PageText], *, target_tokens: int = 500, overlap_sentences: int = 2
) -> list[ChunkResult]:
    """
    Packs sentences into chunks up to target_tokens and then startsteh next chunk 
    by including the last overlap_sentences sentences
    
    A chunk's page_number is its first sentence's source page.. Slightly oversized sentence is kept whole rather than truncated
    """

    sentences = _sentences_with_pages(pages)
    chunks: list[ChunkResult] = []
    current: list[tuple[str, int]] = []
    current_tokens = 0
    chunk_index = 0

    def flush() -> None:
        nonlocal chunk_index
        if not current:
            return
        text = " ".join(sentence for sentence, _ in current)
        if prose_ratio(text) < _MIN_PROSE_RATIO:
            # Skipped, not indexed: retrieving a table dump helps nobody.
            return
        chunks.append(
            ChunkResult(
                chunk_index=chunk_index,
                page_number=current[0][1],
                text=text,
                token_count=estimate_tokens(text),
            )
        )
        chunk_index += 1
    
    for sentence, page_number in sentences:
        sentence_tokens = estimate_tokens(sentence)
        if current and current_tokens + sentence_tokens > target_tokens:
            flush()
            current = current [-overlap_sentences:] if overlap_sentences else []
            # Drop carried-over sentences big enough to blow the budget on their
            # own. Without this an oversized sentence never leaves the window and
            # gets repeated at the head of every following chunk.
            while current and sum(estimate_tokens(s) for s, _ in current) > target_tokens // 2:
                current.pop(0)
            current_tokens = sum(estimate_tokens(s) for s, _ in current)
        
        current.append((sentence, page_number))
        current_tokens += sentence_tokens
    
    flush()
    return chunks