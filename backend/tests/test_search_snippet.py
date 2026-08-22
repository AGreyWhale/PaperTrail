from app.services.search_service import focus_snippet, query_terms

CHUNK = (
    "The Astrophysical Journal, 989:44 (23pp), 2025 August 10.\n"
    "We present rest-frame radio SEDs of a sample of 160 star-forming galaxies.\n"
    "The spectral index steepens towards higher frequencies in these sources. "
    "MeerKAT observations combined with archival Very Large Array data were used. "
    "We conclude that free-free emission contributes little at these frequencies."
)


def test_snippet_centres_on_the_matching_sentence():
    snippet = focus_snippet(CHUNK, "spectral index steepens")

    assert "spectral index steepens" in snippet
    # Not the whole chunk — that was the bug.
    assert len(snippet) < len(CHUNK)


def test_snippet_marks_where_it_was_trimmed():
    snippet = focus_snippet(CHUNK, "free-free emission", max_chars=120)

    assert snippet.startswith("… ")


def test_snippet_collapses_newlines_so_it_reads_as_one_passage():
    assert "\n" not in focus_snippet(CHUNK, "radio SEDs")


def test_snippet_falls_back_to_the_opening_for_a_purely_semantic_match():
    # No shared words at all, which is normal for embedding search.
    snippet = focus_snippet(CHUNK, "zzzz qqqq")

    assert snippet.startswith("The Astrophysical Journal")


def test_snippet_respects_the_character_budget():
    assert len(focus_snippet(CHUNK, "MeerKAT", max_chars=100)) <= 110


def test_snippet_handles_text_with_no_sentence_breaks():
    assert focus_snippet("no punctuation here at all", "punctuation")


def test_common_words_are_not_treated_as_search_terms():
    # Otherwise "the" would pick a sentence at random.
    assert query_terms("the effect of the model") == {"effect", "model"}
