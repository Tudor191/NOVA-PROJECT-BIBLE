#!/usr/bin/env python3
"""Apply versioned Cypher constraint/index scripts in this directory, in
filename order (docs/architecture/07-database-architecture.md §7's "versioned
Cypher migration scripts (Neo4j), gated in CI").

Deliberately outside `src/nova_world_model_engine/` and talks to the `neo4j`
driver directly -- schema DDL is a migration-tooling concern, not something the
abstracted `GraphStore` interface exposes (ADR-007 has no raw-Cypher-execute
method by design), the same split Knowledge Engine's own `cypher/
apply_constraints.py` uses.

Usage:
    uv run --package world-model-engine python cypher/apply_constraints.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

CYPHER_DIR = Path(__file__).resolve().parent


def _statements(text: str) -> list[str]:
    lines = [line for line in text.splitlines() if not line.strip().startswith("//")]
    stripped = "\n".join(lines)
    return [s.strip() for s in stripped.split(";") if s.strip()]


async def _apply() -> None:
    from neo4j import AsyncGraphDatabase

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "nova_dev_password")

    scripts = sorted(CYPHER_DIR.glob("*.cypher"))
    if not scripts:
        print("No .cypher scripts found.")
        return

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            for script in scripts:
                for statement in _statements(script.read_text()):
                    await session.run(statement)
                print(f"Applied {script.name}")
    finally:
        await driver.close()


def main() -> int:
    import asyncio

    asyncio.run(_apply())
    return 0


if __name__ == "__main__":
    sys.exit(main())
