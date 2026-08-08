"""`domain.conversation_memory` (design doc Sec0.8/Sec9) -- applying
`memory_annotations` onto a `ConversationMemory`."""

from __future__ import annotations

from nova_communication_engine.domain.conversation_memory import apply_memory_annotations
from nova_communication_engine.domain.models import ConversationMemory


def test_no_annotations_returns_the_same_memory_unchanged() -> None:
    memory = ConversationMemory(decisions=["existing"])

    result = apply_memory_annotations(memory, annotations=None)

    assert result == memory


def test_a_valid_annotation_appends_to_its_named_category() -> None:
    memory = ConversationMemory()

    result = apply_memory_annotations(
        memory, annotations=[{"category": "decisions", "text": "chose option B"}]
    )

    assert result.decisions == ["chose option B"]
    assert result.preferences == []
    assert result.corrections == []
    assert result.feedback == []


def test_multiple_annotations_across_categories_all_apply() -> None:
    memory = ConversationMemory()

    result = apply_memory_annotations(
        memory,
        annotations=[
            {"category": "preferences", "text": "prefers terse responses"},
            {"category": "corrections", "text": "actually meant Tuesday"},
            {"category": "feedback", "text": "liked the summary"},
        ],
    )

    assert result.preferences == ["prefers terse responses"]
    assert result.corrections == ["actually meant Tuesday"]
    assert result.feedback == ["liked the summary"]


def test_existing_entries_are_preserved_not_overwritten() -> None:
    memory = ConversationMemory(decisions=["first decision"])

    result = apply_memory_annotations(
        memory, annotations=[{"category": "decisions", "text": "second decision"}]
    )

    assert result.decisions == ["first decision", "second decision"]


def test_an_unrecognized_category_is_dropped_not_raised() -> None:
    memory = ConversationMemory()

    result = apply_memory_annotations(
        memory, annotations=[{"category": "objective", "text": "should not apply"}]
    )

    assert result == memory


def test_a_missing_text_field_is_dropped_not_raised() -> None:
    memory = ConversationMemory()

    result = apply_memory_annotations(memory, annotations=[{"category": "decisions"}])

    assert result.decisions == []
