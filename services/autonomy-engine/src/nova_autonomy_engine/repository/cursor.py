"""The opaque keyset cursor -- TDD 4D §8.1/§9: *"keyset paginated on an opaque
cursor, **no offset**"*.

Its own module because three places must agree on the format exactly: the
Postgres repository that mints and seeks on it, the in-memory fake the default
test tier runs against, and the API layer that turns a malformed one into a
422. A codec duplicated across those three is a codec that eventually differs
in one of them.

**Opaque is the point.** The encoding is not a secret, but a client that cannot
read `(created_at, id)` out of a cursor also cannot construct an arbitrary one
-- and therefore cannot reconstruct offset pagination on top of a keyset API,
which is the failure mode §9 forbids.

**A malformed cursor is rejected, never ignored.** Treating it as "start from
the beginning" would turn a client bug into a silently duplicated page.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from uuid import UUID

__all__ = ["InvalidCursorError", "decode_cursor", "encode_cursor"]


class InvalidCursorError(ValueError):
    """A cursor this service did not mint."""


def encode_cursor(created_at: datetime, row_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{row_id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        moment, separator, row_id = raw.partition("|")
        if not separator:
            raise ValueError("missing separator")
        return datetime.fromisoformat(moment), UUID(row_id)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise InvalidCursorError(f"not a cursor this service issued: {cursor!r}") from exc
