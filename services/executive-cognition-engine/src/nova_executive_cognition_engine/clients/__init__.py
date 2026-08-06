"""Adapters for every upstream RPC this engine calls (docs/design/phase-2c/
00-executive-cognition-engine.md §1, §5) -- the directory that knows each
upstream engine's wire shape, but imports no provider SDK: every call here
goes through the Event Bus (ADR-004) via an `EventPublisher`. Each module
implements exactly one `domain/ports.py` Protocol, reusing Reasoning
Engine's own equivalent client's shape structurally (§5.3, §5.5-§5.7) --
independently implemented, never imported across the engine boundary.
"""
