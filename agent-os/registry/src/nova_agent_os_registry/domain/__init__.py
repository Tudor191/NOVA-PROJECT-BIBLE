"""Registry's domain logic.

Framework-free by design (docs/architecture/03-backend-architecture.md §1): this
package must never import FastAPI, SQLAlchemy, or the Event Bus SDK directly. It
depends on ports defined here; `events/` and `repository/` implement them.
"""
