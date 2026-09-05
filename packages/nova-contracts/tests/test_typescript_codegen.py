"""Tests for the generated TypeScript contract surface (`typescript/`).

**Why this file exists.** The generated output had never been type-checked by
anything: the codegen pipeline had zero consumers, there was no `tsconfig.json`
anywhere in the repository, and TypeScript was not installed. A `tsc --noEmit`
pass run during Phase 4A pre-work reported **395 `TS2308` errors**, every one of
them in the generated barrel.

**Root cause.** Pydantic's `model_json_schema()` gives every property a `title`
derived from its field name (`schema_version` -> `"Schema Version"`).
`json-schema-to-typescript` promotes each titled property to its own *exported*
top-level alias, so `export type SchemaVersion = number;` is emitted into nearly
every module. `schema_version` is on 94 of the 97 payload models; `correlation_id`
is on 31 and `user_id` on 25. A barrel assembled from `export * from "./X"` lines
re-exports all of those incidental aliases into one namespace, where the
same-named-but-unrelated aliases collide -- exactly what TS2308 reports.

Merging or de-duplicating the aliases would be wrong: `Status` in
`ActionResultPayload` is an eight-member union while `Status` elsewhere is a
plain string. They share a name and nothing else. The fix is therefore to export
only each module's root interface from the barrel, by name.

These tests assert the invariants that keep that true. They are deliberately
pure-Python and read the committed generated output, so they run in the ordinary
`pytest` suite with no Node toolchain required; the `tsc --noEmit` check itself
is wired separately in CI against `packages/nova-contracts/tsconfig.json`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TS_DIR = PACKAGE_ROOT / "typescript"
INDEX = TS_DIR / "index.ts"

_EXPORT_LINE = re.compile(r'^export type \{ (?P<name>\w+) \} from "\./(?P<module>\w+)";$')
# MULTILINE matters: without it `^` anchors to the start of the whole file and
# only the first declaration in each module is ever seen.
_ANY_EXPORT = re.compile(
    r"^export (?:interface|type|const|enum|declare) (\w+)", re.MULTILINE
)


def _payload_modules() -> list[Path]:
    return sorted(p for p in TS_DIR.glob("*.ts") if p.name != "index.ts")


def test_generated_output_exists() -> None:
    modules = _payload_modules()
    assert modules, "no generated TypeScript contracts found -- run the codegen"
    assert INDEX.exists(), "the barrel index.ts is missing"


def test_barrel_never_uses_star_exports() -> None:
    """`export *` is what produced the 395 TS2308 collisions. It must not return.

    This is the single assertion that would have caught the original defect.
    """
    offending = [
        line
        for line in INDEX.read_text().splitlines()
        if line.strip().startswith("export *")
    ]
    assert not offending, (
        "index.ts uses `export *`, which re-exports json2ts's per-property "
        f"aliases and collides across modules (TS2308). Offending lines: {offending}"
    )


def test_barrel_exports_exactly_one_name_per_module() -> None:
    lines = [line for line in INDEX.read_text().splitlines() if line.strip()]
    modules = {p.stem for p in _payload_modules()}

    parsed = []
    for line in lines:
        match = _EXPORT_LINE.match(line)
        assert match is not None, f"unrecognised barrel line: {line!r}"
        parsed.append((match["name"], match["module"]))

    # Each line re-exports the interface that shares its module's name.
    for name, module in parsed:
        assert name == module, (
            f"barrel exports {name!r} from module {module!r}; the barrel must "
            "re-export only each module's own root interface"
        )

    exported_modules = {module for _, module in parsed}
    assert exported_modules == modules, (
        "barrel and generated modules disagree. "
        f"missing from barrel: {sorted(modules - exported_modules)}; "
        f"barrel references no such module: {sorted(exported_modules - modules)}"
    )


def test_barrel_has_no_duplicate_exported_symbols() -> None:
    names = [
        match["name"]
        for line in INDEX.read_text().splitlines()
        if (match := _EXPORT_LINE.match(line)) is not None
    ]
    duplicates = {name for name in names if names.count(name) > 1}
    assert not duplicates, f"duplicate exported symbols in the barrel: {sorted(duplicates)}"


def test_every_module_exports_its_own_root_interface() -> None:
    """The barrel's named re-exports are only valid if this holds for every module."""
    missing = [
        path.name
        for path in _payload_modules()
        if not re.search(
            rf"^export interface {re.escape(path.stem)}\b", path.read_text(), re.MULTILINE
        )
    ]
    assert not missing, f"modules with no self-named root interface: {missing}"


def test_property_aliases_really_do_collide() -> None:
    """Negative control for the invariant above.

    If json2ts ever stopped emitting per-property aliases, `export *` would
    become harmless and `test_barrel_never_uses_star_exports` would be guarding
    nothing. This test fails in that case, forcing the guard to be re-justified
    rather than silently becoming decorative.
    """
    counts: dict[str, int] = {}
    for path in _payload_modules():
        for name in set(_ANY_EXPORT.findall(path.read_text())):
            counts[name] = counts.get(name, 0) + 1

    colliding = {name: n for name, n in counts.items() if n > 1}
    assert colliding, (
        "no exported name appears in more than one generated module, so the "
        "`export *` prohibition no longer guards anything -- re-justify it"
    )
    # `schema_version` is on nearly every payload model, so its alias is the
    # single worst offender and the clearest signal that the hazard is real.
    assert counts.get("SchemaVersion", 0) > 1, (
        "SchemaVersion no longer collides; the codegen's shape has changed "
        "materially and this guard needs review"
    )


@pytest.mark.parametrize("forbidden", ["export * from", "export *"])
def test_no_module_reexports_another_module(forbidden: str) -> None:
    """Payload modules are standalone; only the barrel aggregates them."""
    offenders = [p.name for p in _payload_modules() if forbidden in p.read_text()]
    assert not offenders, f"payload modules must not re-export: {offenders}"


def test_every_registered_payload_reaches_the_typescript_surface() -> None:
    """`MODELS` in the codegen is hand-maintained, and drifts silently.

    A payload decorated with `@register_payload` is live on the bus the
    moment an engine publishes it, but it only acquires a TypeScript type if
    someone also remembered to add it to `codegen/generate_typescript.py`'s
    `MODELS` list. Nothing connected those two facts, so a new contract could
    ship to every Python consumer while the web client had no type for it --
    and the failure is invisible, because the generator happily reports
    success for the models it *was* given.

    Phase 4A hit exactly this: `CommunicationIntentDeliveredPayload` was
    registered, published, and covered by engine tests, and the regenerated
    output still contained 97 files rather than 98.
    """
    from nova_contracts import registry

    generated = {p.stem for p in _payload_modules()}
    missing = sorted(
        model.__name__
        for subject in registry.known_subjects()
        if (model := registry.payload_model_for(subject)) is not None
        # The registry is process-global, so other tests in this suite
        # register throwaway models into it. Only models that actually ship
        # from this package are supposed to have a generated counterpart.
        and model.__module__.startswith("nova_contracts.")
        and model.__name__ not in generated
    )
    assert not missing, (
        f"registered payloads with no generated TypeScript type: {missing}. "
        "Add each to MODELS in packages/nova-contracts/codegen/"
        "generate_typescript.py and re-run the generator."
    )
