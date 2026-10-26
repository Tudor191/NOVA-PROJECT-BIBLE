"""The 85% domain-coverage gate (doc 16 §1, finding N-11) is real and exact.

Two ways the gate has been silently weaker than it reads:

* **No package was measured against it** until `COVERAGE_RCFILE` pointed each
  package-directory run at the root config. A package can still drop out the
  same way by losing `--cov` from its `test` script.
* **It rounded.** coverage.py fails a run only when
  `round(total, precision) < fail_under`. At the default precision 0,
  `world-model-engine` measured 84.55% (394 of 466 statements plus branches),
  printed "FAIL Required test coverage of 85.0% not reached", and exited 0.

So this file checks the configuration and the decision function coverage.py
actually uses, not the report text.
"""

from __future__ import annotations

import json
import math
import tomllib
from pathlib import Path

import pytest
import yaml
from coverage.results import should_fail_under

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["tool"]["coverage"]["report"]
THRESHOLD = REPORT["fail_under"]
#: coverage.py's own default when the key is absent.
PRECISION = REPORT.get("precision", 0)

#: Statements plus branches. The largest `domain/` today is about 900; the
#: guarantee below is checked two orders of magnitude past that.
LARGEST_PACKAGE_CHECKED = 100_000


def _largest_total_below_threshold(units: int) -> float:
    """The highest coverage strictly below 85% a package of `units` can measure."""
    covered = math.ceil(0.85 * units) - 1
    total = 100.0 * covered / units
    return total if total < 85 else 100.0 * (covered - 1) / units


def test_the_threshold_is_85_percent() -> None:
    assert THRESHOLD == 85


def test_the_measured_84_55_percent_fails() -> None:
    """The negative control: `world-model-engine` on `phase-4` at `a7d52c1`."""
    total = 100.0 * 394 / 466
    assert round(total, 2) == 84.55
    assert should_fail_under(total, THRESHOLD, PRECISION)


def test_exactly_85_percent_passes() -> None:
    assert not should_fail_under(85.0, THRESHOLD, PRECISION)


@pytest.mark.parametrize("total", [84.994, 84.995, 84.9951, 84.999])
def test_totals_that_round_to_85_at_two_decimals_still_fail(total: float) -> None:
    assert should_fail_under(total, THRESHOLD, PRECISION)


def test_no_total_below_85_percent_passes_for_any_package_size() -> None:
    """At precision 2 a package of 1,013 units can measure 84.99506% and pass;
    the precision must be high enough that no package size up to
    `LARGEST_PACKAGE_CHECKED` can reach the rounding band."""
    passing = [
        units
        for units in range(1, LARGEST_PACKAGE_CHECKED + 1)
        if not should_fail_under(_largest_total_below_threshold(units), THRESHOLD, PRECISION)
    ]
    assert passing == [], f"{len(passing)} package sizes pass below 85%, first {passing[:3]}"


def _domain_packages() -> list[tuple[Path, str]]:
    found = []
    for domain in sorted(REPO_ROOT.glob("*/*/src/*/domain")):
        if domain.is_dir() and (domain / "__init__.py").exists():
            found.append((domain.parents[2], domain.parent.name))
    return found


def test_domain_packages_are_discovered() -> None:
    names = {package.name for package, _ in _domain_packages()}
    assert {"api-gateway", "ws-gateway", "world-model-engine", "kernel"} <= names


@pytest.mark.parametrize(
    ("package", "module"),
    _domain_packages(),
    ids=lambda value: value.name if isinstance(value, Path) else value,
)
def test_every_domain_package_is_measured_against_the_gate(package: Path, module: str) -> None:
    script = json.loads((package / "package.json").read_text())["scripts"]["test"]
    assert f"--cov={module}.domain" in script.split(), (
        f"{package.relative_to(REPO_ROOT)}'s test script does not measure {module}.domain"
    )


def test_ci_points_every_test_task_at_the_root_coverage_config() -> None:
    turbo = json.loads((REPO_ROOT / "turbo.json").read_text())
    assert "COVERAGE_RCFILE" in turbo["tasks"]["test"]["env"]

    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/pr-checks.yml").read_text())
    steps = [
        step
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if step.get("run", "").strip() == "pnpm turbo run test"
    ]
    assert len(steps) == 1
    assert steps[0]["env"]["COVERAGE_RCFILE"] == "${{ github.workspace }}/pyproject.toml"
