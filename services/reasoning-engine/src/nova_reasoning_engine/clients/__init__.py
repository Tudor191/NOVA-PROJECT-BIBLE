"""Adapters for every upstream RPC this engine calls (docs/design/phase-2b/
00-reasoning-engine.md §1, §7) -- the directory that knows each upstream
engine's wire shape, but (unlike `connectors/`, ADR-020's sole home for
provider SDK imports) imports no provider SDK: every call here goes through
the Event Bus (ADR-004) via an `EventPublisher`. Each module implements
exactly one `domain/ports.py` Protocol.
"""
