// Initial Neo4j constraints/indexes -- docs/design/phase-1/02-knowledge-engine.md §5.
// Applied via apply_constraints.py, never through the abstracted `GraphStore`
// interface (ADR-007 deliberately has no raw-Cypher-execute method -- schema
// DDL is an operational concern, the same split Alembic already has from the
// application's ORM session on the Postgres side).
//
// Idempotent (`IF NOT EXISTS`) -- safe to re-run.

CREATE CONSTRAINT knowledge_node_id_unique IF NOT EXISTS
    FOR (n:Concept|Technology|Framework|ProgrammingLanguage|Company|Person|Project|Document|API|Database|Pattern|Decision)
    REQUIRE n.id IS UNIQUE;

CREATE INDEX concept_name_idx IF NOT EXISTS FOR (c:Concept) ON (c.name);

CREATE FULLTEXT INDEX knowledge_fulltext IF NOT EXISTS
    FOR (n:Concept|Technology|Project|Document) ON EACH [n.name];
