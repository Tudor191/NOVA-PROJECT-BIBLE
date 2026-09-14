"""The append-only guarantee and the no-offset rule, asserted **mechanically**.

TDD §9: *"`decision_log` is append-only. No `UPDATE`, no `DELETE` ... Asserted
by a test that inspects the repository for the absence of those methods, as
`agent-os/kernel` does."* and *"Keyset pagination on `(created_at DESC, id
DESC)`; **no offset anywhere**."*

Inspecting for absence is what makes this survive a refactor: a future edit
that adds `delete_decision_log` to any implementation fails here without anyone
needing to remember the rule.
"""

from __future__ import annotations

import inspect

import pytest
from nova_autonomy_engine.domain.ports import FORBIDDEN_REPOSITORY_METHODS, AutonomyRepository
from nova_autonomy_engine.repository.postgres_autonomy_repository import (
    PostgresAutonomyRepository,
)

from tests.fakes.repository import FakeAutonomyRepository

_IMPLEMENTATIONS = [AutonomyRepository, PostgresAutonomyRepository, FakeAutonomyRepository]


@pytest.mark.parametrize("implementation", _IMPLEMENTATIONS)
@pytest.mark.parametrize("forbidden", sorted(FORBIDDEN_REPOSITORY_METHODS))
def test_no_implementation_can_mutate_or_erase_the_decision_log(
    implementation: type, forbidden: str
) -> None:
    """Bible Part 14: *"Store every important autonomous decision."* The
    guarantee is structural -- there is no method to call."""
    assert not hasattr(implementation, forbidden)


@pytest.mark.parametrize("implementation", _IMPLEMENTATIONS)
def test_no_implementation_exposes_a_generic_mutation_escape_hatch(
    implementation: type,
) -> None:
    """A method named for raw SQL or bulk deletion would route around the
    absence above."""
    names = {name for name in dir(implementation) if not name.startswith("_")}
    assert not {name for name in names if "execute_sql" in name or "raw" in name}
    assert not {name for name in names if name.startswith("truncate")}
    assert not {name for name in names if name.startswith("delete") and "log" in name}


@pytest.mark.parametrize("implementation", _IMPLEMENTATIONS)
def test_list_suggestions_offers_a_cursor_and_no_offset(implementation: type) -> None:
    """TDD §8.1/§9: an `offset` parameter anywhere in the pagination surface
    fails here, in every implementation at once."""
    signature = inspect.signature(implementation.list_suggestions)
    assert "cursor" in signature.parameters
    assert "offset" not in signature.parameters
    assert "skip" not in signature.parameters
    assert "page" not in signature.parameters


@pytest.mark.parametrize("implementation", _IMPLEMENTATIONS)
def test_no_method_anywhere_accepts_an_offset(implementation: type) -> None:
    """The rule is *"no offset anywhere"*, not "no offset on the one method we
    remembered to check"."""
    for name in dir(implementation):
        if name.startswith("_"):
            continue
        member = getattr(implementation, name)
        if not callable(member):
            continue
        parameters = set(inspect.signature(member).parameters)
        assert "offset" not in parameters, f"{implementation.__name__}.{name}"


def test_the_shipped_repository_satisfies_the_protocol() -> None:
    assert isinstance(
        PostgresAutonomyRepository(session_factory=None),  # type: ignore[arg-type]
        AutonomyRepository,
    )


def test_the_fake_satisfies_the_same_protocol() -> None:
    """So a test passing against the fake is testing the same surface the
    engine runs in production -- the part a fake *can* stand in for."""
    assert isinstance(FakeAutonomyRepository(), AutonomyRepository)
