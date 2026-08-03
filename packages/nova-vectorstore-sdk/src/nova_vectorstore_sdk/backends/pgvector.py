"""pgvector `VectorStore` backend -- the default implementation (ADR-010: every
`VECTOR(...)` column in Phase 1's schemas is `VECTOR(768)`, indexed HNSW per
docs/design/phase-1/01-memory-engine.md §9).

Unlike a standalone vector database, pgvector columns live directly on tables an
engine's own repository already owns and creates via Alembic (e.g.
`memory.memory_record.embedding`, `knowledge.node_metadata.embedding` -- see
docs/design/phase-1/01-memory-engine.md §4 and 02-knowledge-engine.md §4). This
backend therefore never creates, drops, or inserts new rows into a collection's
table -- it only reads and writes the vector (and whitelisted metadata) columns of
rows that already exist. `upsert` on a row that does not yet exist raises
`CollectionRecordNotFoundError` rather than silently inserting a partial row with
whatever NOT NULL columns the owning engine's schema requires but this SDK knows
nothing about.

This module lazily imports `asyncpg` and `pgvector` inside each method (not at
module scope) so that importing `nova_vectorstore_sdk` never requires a Postgres
server to be reachable, mirroring `nova_eventbus_sdk.backends.nats`.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nova_vectorstore_sdk.interface import VectorMatch, VectorQuery, VectorRecord, VectorStoreHealth

if TYPE_CHECKING:
    from asyncpg import Pool

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


class CollectionRecordNotFoundError(LookupError):
    """Raised by `PgVectorStore.upsert` when the target row does not already exist.

    Every collection maps to a table owned by another engine's schema (never a table
    this SDK creates), so there is no safe generic INSERT path -- see module
    docstring.
    """


def _validate_identifier(name: str) -> str:
    """Table/column names are inlined into SQL (Postgres has no way to parameterize
    an identifier), so every one is validated against a strict allow-list pattern
    before use -- defense against a misconfigured `PgVectorCollection` becoming a SQL
    injection vector, even though these values come from trusted application config,
    not user input."""
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


@dataclass(frozen=True)
class PgVectorCollection:
    """Maps a logical collection name to a table this SDK does not own.

    `metadata_columns` whitelists which additional columns `upsert`'s
    `record.metadata` may write and `search`'s `query.filters` may filter on; any
    other key is rejected -- both to avoid a class of SQL-injection-via-column-name
    and to keep the mapping explicit rather than inferred from a table's schema at
    runtime.
    """

    table: str
    id_column: str = "id"
    vector_column: str = "embedding"
    metadata_columns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier(self.table)
        _validate_identifier(self.id_column)
        _validate_identifier(self.vector_column)
        for column in self.metadata_columns:
            _validate_identifier(column)


class PgVectorStore:
    """`VectorStore` implementation backed by Postgres + the pgvector extension."""

    def __init__(self, dsn: str, collections: dict[str, PgVectorCollection]) -> None:
        self._dsn = dsn
        self._collections = collections
        self._pool: Pool | None = None

    async def connect(self) -> None:
        import asyncpg
        from pgvector.asyncpg import register_vector

        async def _init(conn: object) -> None:
            await register_vector(conn)

        self._pool = await asyncpg.create_pool(self._dsn, init=_init)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def _collection(self, name: str) -> PgVectorCollection:
        try:
            return self._collections[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._collections)) or "(none registered)"
            raise ValueError(
                f"Unknown collection {name!r}. Registered collections: {available}."
            ) from exc

    async def upsert(self, collection: str, record: VectorRecord) -> None:
        await self.upsert_batch(collection, [record])

    async def upsert_batch(self, collection: str, records: list[VectorRecord]) -> None:
        pool = self._require_connected()
        config = self._collection(collection)
        present_keys = _all_metadata_keys(records)
        unknown_keys = present_keys - set(config.metadata_columns)
        if unknown_keys:
            raise ValueError(
                f"Metadata key(s) {sorted(unknown_keys)} are not whitelisted for "
                f"collection {collection!r}. Whitelisted: {config.metadata_columns}."
            )
        extra_columns = [c for c in config.metadata_columns if c in present_keys]
        set_clause = ", ".join(
            [f"{config.vector_column} = $2"]
            + [f"{col} = ${i + 3}" for i, col in enumerate(extra_columns)]
        )
        query = (
            f"UPDATE {config.table} SET {set_clause} WHERE {config.id_column} = $1"  # noqa: S608
        )
        async with pool.acquire() as conn, conn.transaction():
            for record in records:
                args = [record.id, record.vector] + [
                    record.metadata.get(col) for col in extra_columns
                ]
                result = await conn.execute(query, *args)
                if result == "UPDATE 0":
                    raise CollectionRecordNotFoundError(
                        f"No row with {config.id_column}={record.id!r} exists in "
                        f"{config.table!r}. PgVectorStore only updates existing rows "
                        f"-- see module docstring."
                    )

    async def search(self, collection: str, query: VectorQuery) -> list[VectorMatch]:
        pool = self._require_connected()
        config = self._collection(collection)
        for key in query.filters:
            if key not in config.metadata_columns:
                raise ValueError(
                    f"{key!r} is not a whitelisted metadata column for collection "
                    f"{collection!r}. Whitelisted: {config.metadata_columns}."
                )
        where_clauses = [f"{config.vector_column} IS NOT NULL"]
        args: list[object] = [query.vector]
        for i, (key, value) in enumerate(query.filters.items()):
            where_clauses.append(f"{key} = ${i + 2}")
            args.append(value)
        where_sql = " AND ".join(where_clauses)
        select_columns = ", ".join(
            [config.id_column, f"1 - ({config.vector_column} <=> $1) AS score"]
            + list(config.metadata_columns)
        )
        sql = (
            f"SELECT {select_columns} FROM {config.table} "  # noqa: S608
            f"WHERE {where_sql} ORDER BY {config.vector_column} <=> $1 LIMIT {int(query.top_k)}"
        )
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        matches = [
            VectorMatch(
                id=str(row[config.id_column]),
                score=float(row["score"]),
                metadata={col: row[col] for col in config.metadata_columns},
            )
            for row in rows
        ]
        if query.min_score is not None:
            matches = [m for m in matches if m.score >= query.min_score]
        return matches

    async def delete(self, collection: str, id: str) -> None:
        """Null out `id`'s vector column, removing it from the HNSW partial index
        (`WHERE embedding IS NOT NULL`, per docs/design/phase-1/01-memory-engine.md
        §9). Never deletes the row -- row lifecycle belongs to the owning engine."""
        pool = self._require_connected()
        config = self._collection(collection)
        sql = (
            f"UPDATE {config.table} SET {config.vector_column} = NULL "  # noqa: S608
            f"WHERE {config.id_column} = $1"
        )
        async with pool.acquire() as conn:
            await conn.execute(sql, id)

    async def health(self) -> VectorStoreHealth:
        if self._pool is None:
            return VectorStoreHealth(connected=False, backend="pgvector")
        start = time.perf_counter()
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT 1")
            latency_ms = (time.perf_counter() - start) * 1000
            return VectorStoreHealth(connected=True, backend="pgvector", latency_ms=latency_ms)
        except Exception as exc:  # noqa: BLE001 -- health checks must never raise
            return VectorStoreHealth(connected=False, backend="pgvector", error=str(exc))

    def _require_connected(self) -> Pool:
        if self._pool is None:
            raise RuntimeError("PgVectorStore.connect() must be called before use.")
        return self._pool


def _all_metadata_keys(records: list[VectorRecord]) -> set[str]:
    keys: set[str] = set()
    for record in records:
        keys.update(record.metadata)
    return keys
