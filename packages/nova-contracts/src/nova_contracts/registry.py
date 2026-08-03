"""Payload schema registry: maps event subjects to their Pydantic payload model.

An engine's `events/published.py` registers every subject it emits by decorating
the payload model with `@register_payload("some.subject")`. This is what CI's
contract tests (docs/architecture/16-testing-strategy.md #4) validate against, and
what `nova-eventbus-sdk` uses to reject publishing an undeclared subject
(docs/architecture/09-event-bus-architecture.md #6).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

_ModelT = TypeVar("_ModelT", bound=type[BaseModel])

_REGISTRY: dict[str, type[BaseModel]] = {}


def register_payload(subject: str) -> Callable[[_ModelT], _ModelT]:
    """Class decorator registering a Pydantic model as the payload schema for `subject`."""

    def _decorator(model: _ModelT) -> _ModelT:
        existing = _REGISTRY.get(subject)
        if existing is not None and existing is not model:
            raise ValueError(
                f"Subject {subject!r} is already registered to {existing.__name__}; "
                f"cannot also register {model.__name__}."
            )
        _REGISTRY[subject] = model
        return model

    return _decorator


def payload_model_for(subject: str) -> type[BaseModel] | None:
    """Return the registered payload model for `subject`, or None if unregistered."""
    return _REGISTRY.get(subject)


def validate_payload(subject: str, payload: dict[str, Any]) -> BaseModel | dict[str, Any]:
    """Validate `payload` against its registered schema, if one exists.

    Unregistered subjects pass through unvalidated -- this keeps the registry additive
    (a subject can be used experimentally before its schema is formalized) rather than
    a hard gate that blocks all publishing until every subject is registered.
    """
    model = payload_model_for(subject)
    if model is None:
        return payload
    return model.model_validate(payload)


def known_subjects() -> list[str]:
    """Every subject with a registered payload schema, sorted for stable output."""
    return sorted(_REGISTRY)
