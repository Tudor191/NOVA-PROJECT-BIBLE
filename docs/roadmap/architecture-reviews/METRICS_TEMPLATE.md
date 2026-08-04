# Phase N Engineering Metrics

> Standing requirement (established at the Phase 1 Gate Review, permanent going
> forward): every completed phase reports these thirteen metrics, either as a section
> of that phase's gate review / architecture review report, or as a standalone
> companion document linked from it. Every number must come from a command actually
> run against the repository during that phase's review — never estimated,
> extrapolated, or carried over from a prior phase's numbers. If a metric genuinely
> cannot be measured (e.g. no live infrastructure available in the review
> environment), say so explicitly and name what measuring it would require — do not
> fill in a plausible-looking placeholder.

## Total source lines of code

Report production (`src/`) and test (`tests/`) lines separately, plus a total, plus a
per-package/service breakdown. Command: `find <path> -name "*.py" -exec cat {} + | wc -l`.

## Number of modules

Report both: count of first-party packages (workspace members), and count of `.py`
files within them (source and test counted separately).

## Number of public APIs

Report HTTP REST endpoints (route handler count, plus any mounted ASGI apps like a
metrics endpoint) and event-bus-facing contracts (published event types + served
request/reply RPCs) separately — they are different kinds of "public API" and
conflating them hides information.

## Test count

Per-package breakdown plus a total. Command: `pytest --collect-only -q`, per package.
State whether all tests pass, not just how many exist.

## Test coverage

Per-package/service breakdown plus an aggregate. If coverage tooling isn't installed
yet, install it (durably, as a dev dependency, not a one-off) rather than skipping the
metric. Flag any package whose coverage number is a measurement artifact rather than a
real quality signal (e.g. a contracts/schema package exercised mostly by *other*
packages' test suites) — report the number, but don't let it stand uncontextualized in
a headline aggregate.

## ADR count

Total ADRs in the canonical log (`docs/architecture/00-overview-and-decisions.md` +
`docs/architecture/adr/`), with the running total, not just this phase's additions.

## Architecture documents

Count Bible parts, SAD docs, ADR files, phase design docs, and README files
separately, plus a grand total and a total word count for `docs/`.

## Build duration

If no compiled build step exists, report what actually approximates it (dependency
sync time, full test suite wall time) and say so explicitly rather than inventing a
number. Report Docker image build time if a Docker daemon is reachable in the review
environment; state plainly if one isn't, rather than guessing.

## Static analysis results

Linter, type checker, import-boundary linter, and dependency vulnerability scanner
results — each as a pass/fail plus the raw count (files checked, issues found,
contracts kept/broken, vulnerabilities found).

## Dependency graph

Package count, edge count, cycle count — built independently of any existing
import-boundary tool's own scoped contracts (e.g. via `grimp` directly), so the check
validates the *actual* graph, not just the specific rules another tool already
enforces.

## Performance benchmarks

Only report real measurements against real infrastructure. If no live infrastructure
was available during the review, state that explicitly and name the specific
follow-up needed to produce real numbers, rather than restating design-time targets as
if they were measured results.

## Memory usage

Same standard as Performance benchmarks — real measurement or an explicit "not
measured, here's what's needed."

## Startup time

Same standard. If Dockerfiles have `HEALTHCHECK --start-period=...` values, note that
those are configured guesses, not measurements, unless actually verified against a
running container.
