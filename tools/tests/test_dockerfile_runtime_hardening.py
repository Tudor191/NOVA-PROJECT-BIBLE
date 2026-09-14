"""Guard: every scanned image patches its base OS packages at build time.

Trivy scans every `build-and-scan.yml` matrix image at `severity: CRITICAL,HIGH`
with `exit-code: 1` and `ignore-unfixed: true`, so an image whose runtime stage
never upgrades its Debian packages fails the build on the day upstream publishes
a *fixed* CVE against `python:3.12-slim` — which every image in this repository
shares. The remedy is one line, and it is already this repository's convention.

**The convention, and where it comes from.** `97fa103` (2026-08-17) added

    RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

to the runtime stage of all 12 then-existing matrix images to close
CVE-2026-53615. Its commit message states the reasoning this file encodes:

    Every one of the 12 build-and-scan matrix services shares the identical
    `FROM python:3.12-slim` base image (confirmed) [...] the other 10 jobs were
    merely cancelled by the workflow's default fail-fast before reaching their
    own scan step, not actually clean. Fixing only the two currently-visible
    failures would leave the same CVE unaddressed in the other 10 shipped images.

That is the failure mode this file exists to prevent: the matrix has no
`fail-fast: false`, so one red scan cancels its siblings, and an unhardened
image can sit unscanned behind another image's failure for as long as nobody
looks.

**This file exists because the fix did not hold.** `97fa103` patched the 12
files but not `tools/scaffold-engine.py`, whose Dockerfile template was written
2026-08-08 — nine days earlier. Every engine scaffolded since inherited a
runtime stage without the line: `ws-gateway` and `api-gateway` in Phase 4A
(`3c18ed5`), `autonomy-engine` in Phase 4D (`eb48d0f`). Two of the three went on
to fail CI. A hand-applied fix that leaves its generator untouched reintroduces
itself on every future scaffold, so the template is fixed alongside this guard
and the guard covers the generated output too.

**Scope: the matrix, not every Dockerfile on disk.** `97fa103` scoped itself the
same way, and said so — it *"does not modify services/planning-engine's
Dockerfile (not yet in the build-and-scan matrix)"*. The requirement follows the
Trivy gate, and the Trivy gate follows the matrix. `test_build_and_scan_matrix.py`
separately guarantees no Dockerfile silently escapes that matrix, and records the
one deliberate exclusion with its reason; this file therefore inherits its
coverage rather than re-deriving it.

**The matrix is read through `test_build_and_scan_matrix.py`'s parser, not
re-parsed here.** That module is the single source of truth for what the matrix
contains, including the anti-vacuity control proving it did not parse to junk.
Duplicating the YAML walk would create a second definition that could drift from
the first.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_build_and_scan_matrix import _matrix_entries

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The exact line `97fa103` established, reproduced byte-for-byte. Asserted as a
#: literal rather than a regex: every matrix Dockerfile carries this precise
#: string, and a near-miss variant is worth failing on — an image
#: that upgrades packages differently is a second convention to maintain, not a
#: pass.
HARDENING_LINE = "RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*"

#: The runtime stage always starts here. Every image in the matrix shares this
#: base, which is precisely why one CVE against it reddens all of them at once.
RUNTIME_STAGE = "FROM python:3.12-slim"


def _runtime_stage_lines(dockerfile: Path) -> list[str]:
    """The lines after the **last** `FROM python:3.12-slim`.

    Taking the last one is what makes this a runtime-stage check rather than a
    file-wide substring search. These are multi-stage builds whose *builder*
    stage opens with the identical `FROM`, and hardening the builder does
    nothing for the shipped image: the runtime stage copies `/app` out of it and
    starts again from an unpatched base. A naive `in dockerfile_text` check
    would pass on exactly the image that is still vulnerable.
    """
    lines = [line.strip() for line in dockerfile.read_text().splitlines()]
    starts = [i for i, line in enumerate(lines) if line == RUNTIME_STAGE]
    assert starts, (
        f"{dockerfile} has no {RUNTIME_STAGE!r} stage. Either it moved off the "
        f"shared base — in which case this guard needs to learn the new one — or "
        f"this parser is broken. Do not delete the test to make this go away."
    )
    return lines[starts[-1] + 1 :]


@pytest.mark.parametrize(
    "entry", _matrix_entries(), ids=lambda e: e["service"]
)
def test_every_scanned_image_upgrades_its_base_packages(entry: dict) -> None:
    """The property. Trivy fails the build without it, and fail-fast then hides
    every sibling image's result behind that one failure."""
    dockerfile = REPO_ROOT / entry["dockerfile"]
    assert dockerfile.is_file(), f"{entry['dockerfile']} does not exist"

    assert HARDENING_LINE in _runtime_stage_lines(dockerfile), (
        f"{entry['service']}'s runtime stage does not run\n\n"
        f"    {HARDENING_LINE}\n\n"
        f"so its shipped image keeps whatever package versions "
        f"{RUNTIME_STAGE} happens to carry. Trivy scans it at CRITICAL,HIGH "
        f"with exit-code 1, so this fails the build the day Debian publishes a "
        f"fixed CVE against that base — and takes its sibling jobs down with it, "
        f"because the matrix has no fail-fast: false. Add the line to the "
        f"runtime stage, immediately after {RUNTIME_STAGE}, exactly as the other "
        f"images have it (convention established by 97fa103, 2026-08-17)."
    )


def test_the_scaffold_template_emits_the_hardened_runtime_stage() -> None:
    """The root cause, asserted at its source.

    Patching the images without patching the generator is what produced this
    defect three times over. Without this test, the next `scaffold-engine.py`
    run reintroduces it and the parametrized test above only notices once the
    new engine reaches the matrix — which, for Phase 4D's `autonomy-engine`,
    meant a red CI run rather than a failed test.
    """
    template = (REPO_ROOT / "tools" / "scaffold-engine.py").read_text()
    assert HARDENING_LINE in template, (
        "tools/scaffold-engine.py's Dockerfile template does not emit\n\n"
        f"    {HARDENING_LINE}\n\n"
        "so every engine scaffolded from it ships an unpatched base image. This "
        "is the defect's origin: 97fa103 fixed the images of 2026-08-17 and "
        "left the template alone, and ws-gateway, api-gateway and "
        "autonomy-engine each inherited the hole afterwards."
    )


# --- controls: this file must fail loudly, never silently pass ---------------


def test_the_matrix_parser_returned_a_real_matrix() -> None:
    """Anti-decoration control. `_matrix_entries()` has its own control in
    `test_build_and_scan_matrix.py`; this one guards *this* file specifically,
    because an empty list would make every parametrized case above vanish
    rather than fail."""
    entries = _matrix_entries()
    assert len(entries) >= 15, f"only {len(entries)} matrix entries parsed"
    names = {entry["service"] for entry in entries}
    for expected in ("nova-core", "ws-gateway", "api-gateway"):
        assert expected in names, f"the parsed matrix is missing {expected!r}"


def test_the_runtime_stage_parser_ignores_the_builder_stage() -> None:
    """The parser's one subtle job, asserted rather than assumed.

    These are two-stage builds off one base: the builder opens with
    `FROM python:3.12-slim AS builder` and the runtime stage with the bare
    `FROM python:3.12-slim`. Exact-equality matching is therefore what separates
    them — a `startswith` or an `in` test would match the builder first, and a
    Dockerfile that hardened only its builder would pass while still shipping an
    unpatched runtime image. That is the false negative worth a control of its
    own, since the whole point of the runtime stage is that it starts over from
    the base and copies only `/app` across.
    """
    dockerfile = REPO_ROOT / "services" / "nova-core" / "Dockerfile"
    stages = [line.strip() for line in dockerfile.read_text().splitlines()]
    assert stages.count(f"{RUNTIME_STAGE} AS builder") == 1, (
        "expected a builder stage distinguished by `AS builder`; if the shape "
        "changed, re-check that _runtime_stage_lines still selects the runtime "
        "stage rather than the builder"
    )
    assert stages.count(RUNTIME_STAGE) == 1, (
        "expected exactly one bare runtime `FROM`; if that changed, "
        "_runtime_stage_lines' selection needs rechecking"
    )

    runtime = _runtime_stage_lines(dockerfile)
    assert "RUN pip install --no-cache-dir uv" not in runtime, (
        "_runtime_stage_lines returned builder-stage content"
    )
    assert any(line.startswith("CMD ") for line in runtime), (
        "_runtime_stage_lines did not reach the runtime stage's CMD"
    )
