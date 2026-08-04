"""In-memory test doubles for `domain.ports` -- not shipped in `src/`. Used by
`tests/integration/` to exercise real domain logic, real API routes, and real
worker functions end-to-end without a live Postgres/Redis, matching the same
"fake implementation of a shared Protocol" pattern `nova-eventbus-sdk`'s
`InMemoryEventBus` already established in Phase 0.

These fakes replicate the semantics that matter for correctness (optimistic
concurrency on `update`, `user_id` scoping on `get`, outbox row bookkeeping) --
they are not a performance or persistence stand-in, and `tests/integration/`'s
`test_*_real.py` files (skipped unless real infra is configured) are what actually
validate `PostgresMemoryRepository`/`RedisWorkingMemoryStore` against Postgres/Redis.
"""

from __future__ import annotations
