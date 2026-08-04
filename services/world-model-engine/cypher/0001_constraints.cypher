// Initial Neo4j constraints/indexes -- docs/design/phase-1/03-world-model-engine.md
// §5. Applied via apply_constraints.py, never through the abstracted
// `GraphStore` interface (ADR-007 deliberately has no raw-Cypher-execute
// method -- schema DDL is an operational concern, the same split Alembic
// already has from the application's ORM session on the Postgres side).
//
// Idempotent (`IF NOT EXISTS`) -- safe to re-run.

CREATE CONSTRAINT world_object_id_unique IF NOT EXISTS
    FOR (n:WorldProject|File|Window|Application|Agent|Task|Device|SystemResource)
    REQUIRE n.id IS UNIQUE;

CREATE INDEX world_project_name_idx IF NOT EXISTS FOR (p:WorldProject) ON (p.name);

CREATE FULLTEXT INDEX world_model_fulltext IF NOT EXISTS
    FOR (n:WorldProject|File) ON EACH [n.name, n.path];
