"""Splits already-generated response text into sentence/phrase chunks for
per-chunk `synthesize` calls -- design doc Sec4, Sec13's chunked-call
latency mitigation: the first chunk's audio reaches the Channel Adapter
before later chunks even finish synthesizing, achieving the same perceived
immediacy a transport-level stream would without one (ADR-004 forbids an
actual streaming Event-Bus RPC, design doc Sec0.3).

Intentionally simple -- boundary detection on sentence-ending punctuation,
not an NLP sentence splitter. §0.1's "pass-through, not a policy engine"
discipline applies here too: this module has exactly one job, keep chunks
short enough that synthesis latency per chunk stays low.
"""

from __future__ import annotations

import re

__all__ = ["split_into_chunks"]

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def split_into_chunks(content: str, *, max_chunk_chars: int = 240) -> list[str]:
    """Splits on sentence-ending punctuation first; any resulting piece
    still longer than `max_chunk_chars` (e.g. one very long sentence) is
    further split on the nearest preceding whitespace so no single
    `synthesize` call is ever handed an unbounded chunk."""
    stripped = content.strip()
    if not stripped:
        return []

    sentences = [s for s in _SENTENCE_BOUNDARY.split(stripped) if s]
    chunks: list[str] = []
    for sentence in sentences:
        chunks.extend(_bound_length(sentence, max_chunk_chars))
    return chunks


def _bound_length(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        split_at = remaining.rfind(" ", 0, max_chars)
        if split_at <= 0:
            split_at = max_chars
        pieces.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces
