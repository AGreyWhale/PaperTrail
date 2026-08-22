from app.chunking.chunker import chunk_pages, estimate_tokens
from app.parsing.pdf_parser import PageText


def test_short_text_becomes_a_single_chunk():
    pages = [PageText(page_number=1, text="A short sentence. Another short one.")]

    chunks = chunk_pages(pages, target_tokens=500)

    assert len(chunks) == 1
    assert chunks[0].page_number == 1
    assert chunks[0].chunk_index == 0


def test_long_text_splits_into_multiple_chunks():
    sentence = "This is a test sentence about attention mechanisms in transformers. "
    pages = [PageText(page_number=1, text=sentence * 30)]

    chunks = chunk_pages(pages, target_tokens=100, overlap_sentences=2)

    assert len(chunks) > 1
    # chunk_index should be sequential starting at 0
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunks_carry_the_correct_source_page():
    pages = [
        PageText(page_number=1, text="Content from page one. More page one content."),
        PageText(page_number=2, text="Content from page two. More page two content."),
    ]

    # Small target forces a chunk boundary between the pages
    chunks = chunk_pages(pages, target_tokens=8, overlap_sentences=0)

    page_numbers = [c.page_number for c in chunks]
    assert 1 in page_numbers
    assert 2 in page_numbers
    # Pages should appear in order — no page-2 content chunked before page 1
    assert page_numbers == sorted(page_numbers)


def test_empty_pages_produce_no_chunks():
    pages = [PageText(page_number=1, text=""), PageText(page_number=2, text="   ")]

    chunks = chunk_pages(pages)

    assert chunks == []


def test_overlap_repeats_sentences_across_chunk_boundary():
    sentences = [f"Sentence number {i} about the topic." for i in range(20)]
    pages = [PageText(page_number=1, text=" ".join(sentences))]

    chunks = chunk_pages(pages, target_tokens=40, overlap_sentences=2)

    assert len(chunks) > 1
    # The tail of chunk 0 should reappear at the start of chunk 1
    tail_of_first = chunks[0].text.split(". ")[-2:]
    for fragment in tail_of_first:
        if fragment.strip():
            assert fragment.strip().rstrip(".") in chunks[1].text


def test_estimate_tokens_is_roughly_proportional_to_length():
    short = estimate_tokens("word")
    long = estimate_tokens("word " * 100)
    assert long > short
    assert estimate_tokens("") == 1  # never zero, avoids div-by-zero elsewhere


def test_oversized_sentence_is_not_repeated_in_later_chunks():
    # One sentence far over the budget, then several normal ones. The big one
    # must appear in exactly one chunk, not carried forward by the overlap.
    huge = "Word " * 400 + "end."
    pages = [PageText(page_number=1, text=huge + " " + " ".join(f"Sentence {i}." for i in range(40)))]

    chunks = chunk_pages(pages, target_tokens=200, overlap_sentences=2)

    carrying = [c for c in chunks if c.text.startswith("Word Word")]
    assert len(carrying) == 1


def test_table_dumps_are_not_chunked():
    # What a numeric table looks like after PDF text extraction.
    soup = "41 516610 1.6 0.58 0 0 . . 1 2 7 40.14 30.49 0 0 . . 1 1 4 6 30.28 " * 12
    pages = [PageText(page_number=1, text=soup)]

    assert chunk_pages(pages) == []


def test_ordinary_prose_still_chunks():
    prose = "The model uses a transformer encoder for this task. " * 40
    pages = [PageText(page_number=1, text=prose)]

    assert len(chunk_pages(pages)) > 0


def test_a_chunk_mixing_prose_and_a_few_numbers_is_kept():
    mixed = (
        "We evaluated the model on three benchmarks and report results below. "
        "Accuracy reached 91.4 percent on the first dataset and 88.2 on the second. "
    ) * 12
    pages = [PageText(page_number=1, text=mixed)]

    assert len(chunk_pages(pages)) > 0
