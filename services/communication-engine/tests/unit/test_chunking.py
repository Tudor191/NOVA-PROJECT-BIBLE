"""`domain.chunking.split_into_chunks` (docs/design/phase-2d/
01-communication-engine.md Sec4, Sec13)."""

from __future__ import annotations

from nova_communication_engine.domain.chunking import split_into_chunks


def test_empty_content_produces_no_chunks() -> None:
    assert split_into_chunks("") == []
    assert split_into_chunks("   ") == []


def test_single_sentence_is_one_chunk() -> None:
    assert split_into_chunks("The build finished successfully.") == [
        "The build finished successfully."
    ]


def test_multiple_sentences_split_on_sentence_boundaries() -> None:
    chunks = split_into_chunks("First sentence. Second sentence! Third one?")
    assert chunks == ["First sentence.", "Second sentence!", "Third one?"]


def test_a_very_long_sentence_is_bounded_by_max_chunk_chars() -> None:
    long_sentence = "word " * 100  # 500 chars, no sentence-ending punctuation
    chunks = split_into_chunks(long_sentence.strip() + ".", max_chunk_chars=50)
    assert len(chunks) > 1
    assert all(len(chunk) <= 50 for chunk in chunks)
    # No word is silently dropped across the split.
    assert "".join(chunks).replace(" ", "") == long_sentence.strip().replace(" ", "") + "."


def test_chunk_order_is_preserved() -> None:
    chunks = split_into_chunks("Alpha. Beta. Gamma.")
    assert chunks == ["Alpha.", "Beta.", "Gamma."]
