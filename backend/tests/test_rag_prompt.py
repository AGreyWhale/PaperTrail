from app.services.rag_service import build_rag_prompt


def test_prompt_includes_question():
    prompt = build_rag_prompt("What method did they use?", [])
    assert "What method did they use?" in prompt


def test_prompt_includes_excerpt_text_and_page_numbers():
    chunks = [
        {"chunk_id": "a", "text": "They used a transformer architecture.", "page_number": 3},
        {"chunk_id": "b", "text": "Results improved by 12%.", "page_number": 7},
    ]

    prompt = build_rag_prompt("What method did they use?", chunks)

    assert "They used a transformer architecture." in prompt
    assert "page 3" in prompt
    assert "Results improved by 12%." in prompt
    assert "page 7" in prompt


def test_prompt_numbers_excerpts_in_order():
    chunks = [
        {"chunk_id": "a", "text": "First excerpt.", "page_number": 1},
        {"chunk_id": "b", "text": "Second excerpt.", "page_number": 2},
    ]

    prompt = build_rag_prompt("A question", chunks)

    assert prompt.index("Excerpt 1") < prompt.index("Excerpt 2")
    assert prompt.index("First excerpt.") < prompt.index("Second excerpt.")
