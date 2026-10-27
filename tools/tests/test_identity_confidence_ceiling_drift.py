"""Guard: `action-engine`'s writable threshold ceiling must track
`perception-engine`'s `SINGLE_SIGNAL_CONFIDENCE_CEILING`.

Phase 4F.4 gave `action-engine` a write surface for `IdentityConfidencePolicy`
(CF-9). A threshold above the highest confidence any identity signal can
actually produce would store a policy that looks configured and can never admit
anything, so the surface rejects one — which means `action-engine` needs to know
that number.

**It must not learn it by importing.** `SINGLE_SIGNAL_CONFIDENCE_CEILING` is
`perception-engine`'s, and ADR-004 forbids one engine importing another's
internals; import-linter's *"Engines are independent"* contract makes that a
structural fact. So `action-engine` declares its own constant, and this file is
what stops the two from silently diverging.

**Both values are read as source text, never imported**, so this guard is
subject to neither the engine-independence contract nor an import cycle — the
same approach the Dockerfile guards in this directory already use to assert
repository-wide invariants without importing what they inspect.

**If fusion (TDD 4F's L-11) ever raises achievable confidence above 0.75**, this
test is what forces that conversation instead of letting `action-engine` keep
rejecting thresholds the system can now meet.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PERCEPTION_SOURCE = (
    REPO_ROOT
    / "services"
    / "perception-engine"
    / "src"
    / "nova_perception_engine"
    / "domain"
    / "identity_fusion.py"
)
ACTION_SOURCE = (
    REPO_ROOT
    / "services"
    / "action-engine"
    / "src"
    / "nova_action_engine"
    / "api"
    / "identity_confidence_policy.py"
)

PERCEPTION_NAME = "SINGLE_SIGNAL_CONFIDENCE_CEILING"
ACTION_NAME = "MAX_CONFIGURABLE_CONFIDENCE"


def _module_level_constant(source: Path, name: str) -> float:
    """The value of a module-level `name = <number>` assignment.

    Parsed from the AST rather than matched with a regex so a value that moved
    into a function, a class or a conditional fails loudly instead of being
    found anyway by a substring search.
    """
    assert source.exists(), f"{source} does not exist"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    for node in tree.body:  # module level only, deliberately
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                assert isinstance(node.value, ast.Constant), (
                    f"{name} in {source.name} is no longer a literal constant"
                )
                return float(node.value.value)

    raise AssertionError(f"{name} is not a module-level constant in {source}")


def test_the_two_ceilings_agree() -> None:
    """The drift guard itself."""
    perception = _module_level_constant(PERCEPTION_SOURCE, PERCEPTION_NAME)
    action = _module_level_constant(ACTION_SOURCE, ACTION_NAME)

    assert action == perception, (
        f"{ACTION_NAME} is {action} but {PERCEPTION_NAME} is {perception}. "
        "action-engine would reject thresholds the identity pipeline can now "
        "reach, or accept ones it cannot. Change both together, and revisit "
        "TDD 4F.4 §16.5 if the achievable confidence has genuinely moved."
    )


def test_the_ceiling_is_still_0_75() -> None:
    """The specific value TDD 4F §5.1, ADR-032 and the 4F.4 ratification all
    reason about. Pinned so a change is a deliberate act with a paper trail,
    not a quiet edit."""
    assert _module_level_constant(PERCEPTION_SOURCE, PERCEPTION_NAME) == 0.75


def test_action_engine_does_not_import_perception_engine() -> None:
    """ADR-004, asserted at the one place 4F.4 could plausibly have broken it.

    The constant is duplicated *because* the import is forbidden; this makes
    sure a later "tidy-up" does not replace the duplication with the violation.
    """
    tree = ast.parse(ACTION_SOURCE.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("nova_perception_engine"), (
                    "action-engine imports perception-engine (ADR-004)"
                )
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("nova_perception_engine"), (
                "action-engine imports perception-engine (ADR-004)"
            )
