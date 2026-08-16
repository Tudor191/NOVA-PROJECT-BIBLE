"""Adapters for every upstream RPC this engine calls -- the directory that
knows each upstream engine's wire shape, but (per ADR-020) imports no
provider SDK: the one call here goes through the Event Bus (ADR-004) via
an `EventPublisher`. Implements exactly one `domain/ports.py` Protocol.
"""
