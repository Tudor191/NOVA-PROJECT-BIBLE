"""The opaque keyset cursor -- TDD §8.1/§9."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from nova_autonomy_engine.repository.cursor import (
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)


def test_a_cursor_round_trips() -> None:
    moment = datetime(2026, 9, 13, 12, 30, tzinfo=UTC)
    row_id = uuid4()
    assert decode_cursor(encode_cursor(moment, row_id)) == (moment, row_id)


def test_a_cursor_does_not_read_as_an_offset() -> None:
    """Opaque is the point: a client that cannot read the keys out of a cursor
    cannot construct an arbitrary one, and therefore cannot rebuild offset
    pagination on top of a keyset API."""
    cursor = encode_cursor(datetime(2026, 9, 13, tzinfo=UTC), uuid4())
    assert not cursor.isdigit()
    assert "2026" not in cursor


@pytest.mark.parametrize(
    "cursor",
    ["", "0", "not-base64!!", "MTIz", "aGVsbG8gd29ybGQ="],
)
def test_a_malformed_cursor_is_rejected_not_ignored(cursor: str) -> None:
    """Treating it as "start from the beginning" would turn a client bug into a
    silently duplicated page."""
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor)
