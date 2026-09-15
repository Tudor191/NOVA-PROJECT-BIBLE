"""The repository port -- the only persistence this engine's domain knows about.

**One port, one store, and it is this engine's own.** TDD 4F §10 and §16
control 11: `cognitive-state-engine` writes its own repository and nothing
else. There is deliberately no port here for reading `memory-engine`,
`world-model-engine` or `digital-twin-engine` state -- those arrive over the
Event Bus (4F.6 onward), never through a database handle this module could be
handed.

**And no port for acting.** TDD 4F §6.2 forbids this engine from publishing
`action.execute`, calling an `action-engine` endpoint or invoking an actuator.
No method here returns or accepts anything that could express one, which is the
structural half of that prohibition; the test half is §16 control 11.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from nova_cognitive_state_engine.domain.models import ActiveThought, AttentionLayer

__all__ = ["CognitiveStateRepository", "ThoughtNotFoundError"]


class ThoughtNotFoundError(LookupError):
    """Raised rather than returning `None` when a caller names a thought that
    does not exist. A domain error type so the API layer can map it without
    matching on exception text -- `autonomy-engine`'s own
    `SuggestionNotFoundError` convention."""


class CognitiveStateRepository(Protocol):
    """Structural, not inherited -- ADR-034's convention, so the domain never
    imports a concrete repository and `nova-service-kit` never imports this
    engine."""

    async def upsert_thought(self, thought: ActiveThought) -> ActiveThought:
        """Insert or replace by `thought_id`, returning the persisted row as it
        was read back.

        Returning the round-tripped value rather than the argument is Phase
        4E's `created_at` lesson made structural: `create_long_term` shipped
        discarding a caller's timestamps precisely because nothing compared
        what went in with what came out."""

    async def get_thought(self, thought_id: UUID) -> ActiveThought:
        """Raises `ThoughtNotFoundError` if absent."""

    async def list_thoughts(
        self, *, user_id: UUID, layer: AttentionLayer | None = None
    ) -> list[ActiveThought]:
        """Every thought for the user, newest-updated first; optionally
        narrowed to one Attention Layer.

        Ordering is `updated_at` descending with `thought_id` as an explicit
        tiebreaker, so a page boundary is reproducible across equal timestamps
        -- the property 4E's real-Postgres tier proved is not provable against
        a fake."""

    async def move_layer(self, thought_id: UUID, layer: AttentionLayer) -> ActiveThought:
        """Persist a layer change decided by `domain/attention.py`.

        **The transition rules are not re-implemented here.** This method
        records a move the domain already validated; putting `next_layer`'s
        table behind a repository call would give the ladder two definitions.
        """
