# Phase N Project Metrics

> Standing requirement (established at the Phase 1 Gate Review, refined immediately
> after into this structure, permanent going forward): every phase report includes a
> Project Metrics section in exactly this shape, either as a section of that phase's
> gate review / architecture review report, or as a standalone companion document
> linked from it. Every number must come from a command actually run against the
> repository during that phase's review — never estimated, extrapolated, or carried
> over from a prior phase's numbers. If a metric genuinely cannot be measured (e.g. no
> live infrastructure available in the review environment), say so explicitly and name
> what measuring it would require — do not fill in a plausible-looking placeholder.
>
> **Recommended tooling**: `cloc` (SLOC excluding blanks/comments, per language,
> `--skip-uniqueness` to avoid silently deduplicating identical scaffolded files),
> `radon cc`/a small `ast`-based script (cyclomatic complexity, function/class size),
> `grimp` (dependency graph / cycle detection, independent of any import-linter-scoped
> contract), and each language's own test runner with coverage plugin (`pytest-cov`
> for Python). Install what's missing as a durable dev dependency rather than
> reporting a metric as unmeasurable because the tool wasn't there.

## Project Statistics — total repository, not implementation size

Distinguish clearly from Implementation Statistics below; these numbers are expected
to be much larger, and that gap is itself informative (e.g. reinstallable caches like
`node_modules`/`.venv` dwarfing the actual versioned content is a healthy sign, not a
concern). Scope to **git-tracked files** for reproducibility — an untracked local
cache isn't part of "the repository," it's regenerable local state that would make the
number environment-dependent.

- **Total files** — `git ls-files | wc -l`.
- **Total directories** — `git ls-files | xargs -n1 dirname | sort -u | wc -l`.
- **Total repository size (MB)** — `git ls-files -z | xargs -0 du -cb | tail -1`,
  converted to MB. Report the `.git` history size separately (it is not working-tree
  content). Optionally report the full on-disk working directory size (including
  build caches) as context for why this distinction matters, clearly labeled as
  informational/environment-dependent, never as the headline number.

## Implementation Statistics

**Production SLOC is the official implementation-size number** (see §10 of
[SAD 15](../../architecture/15-development-workflow.md#10-project-metrics--the-sloc-milestone-gate)
for the 50,000-SLOC milestone gate this number drives). Always excludes blank lines
and comments. Scope precisely and state the scope: application `src/` code plus
database schema migrations (both genuinely ship and run in production); dev tooling
scripts, tests, generated clients, and documentation are each reported as their own
line below, never folded into Production SLOC.

- **SLOC excluding comments and blank lines** — total, across every tracked language.
- **Total comment lines**
- **Comment-to-code ratio** — comment lines ÷ SLOC, as both a ratio and a percentage.
- **Total documentation lines** — Markdown content lines (not blank).
- **Total configuration lines** — YAML + TOML + JSON + INI + Dockerfile content lines
  combined.
- **Total test code SLOC** — everything under a `tests/` directory, any language.
- **Production code SLOC** — see scope note above.
- **Generated code SLOC** (if any) — code produced by a codegen script and committed
  (e.g. a generated TypeScript client). State the source of generation and confirm
  it's current (regenerate and diff before reporting, not just measure whatever is
  on disk) — a stale generated artifact is a real bug this metric should catch, not
  paper over.

## Language Breakdown

SLOC (excluding comments/blanks) per language actually present. Report every language
the template lists even if the count is zero, and add any language present that the
template doesn't list under "Other." If a language's real source is embedded inside
another language's files (e.g. SQL as Python string literals in migration files
rather than standalone `.sql` files), say so explicitly and give an approximate
embedded-line count rather than silently reporting zero.

- Python SLOC
- TypeScript SLOC
- React SLOC (`.tsx`/`.jsx` specifically, if any — distinct from plain TypeScript)
- SQL SLOC (standalone `.sql` files; note embedded SQL separately if none)
- YAML SLOC
- Dockerfile SLOC
- Other languages (name each, e.g. Cypher, Mako, TOML, JSON, INI)

## Architecture Metrics

- Number of modules (report both: first-party packages, and source files within them)
- Number of engines (cognitive/domain services under `services/` specifically —
  e.g. `memory-engine`, `reasoning-engine`, `ai-model-orchestration-engine` —
  distinct from the broader "Number of services" below, which also counts
  gateways/infra services that aren't engines in the Bible's sense)
- Number of services (deployable services vs. shared packages, reported separately)
- Number of APIs (HTTP REST endpoints and event-bus-facing contracts, reported
  separately — they are different kinds of "API")
- Number of database tables (across all schemas)
- Number of graph node types (Neo4j labels, or equivalent)
- Number of graph relationships (relationship *types* defined/actually used, not
  instance counts — and say plainly if a capability exists in code but is not yet
  exercised by any real caller)
- Number of events (published types, served request/reply contracts, and total
  registered payload schemas, reported separately)
- Number of ADRs (running total, not just this phase's additions)
- Number of architecture documents (Bible parts, SAD docs, ADRs, phase design docs,
  READMEs — counted separately, plus a grand total)

## Quality Metrics

- Total tests
- Unit tests
- Integration tests
- End-to-end tests
- Test coverage (per package/service, plus an aggregate over production services only
  — flag any package whose number is a cross-process measurement artifact rather than
  a real quality signal, same as Implementation Statistics' generated-code caveat)
- Ruff status (or the project's linter — pass/fail plus raw issue count)
- MyPy status (or the project's type checker — pass/fail plus files checked)
- Import-linter status (contracts kept/broken, files/dependencies analyzed)

## Growth Metrics

- SLOC added this phase (current cumulative Production SLOC minus the prior phase's
  reported cumulative Production SLOC — if this is the first phase reporting in this
  format, state that plainly rather than fabricating a prior baseline)
- Total cumulative production SLOC
- Total cumulative test SLOC
- Documentation growth (documentation line count, this phase vs. prior)
- ADR growth (ADR count, this phase vs. prior)

**Report cumulative Production SLOC against the 50,000 milestone explicitly** (current
value, percentage of threshold) every phase, even when nowhere close — this is what
makes the milestone a checked gate rather than something watched for informally. Per
[SAD 15 §10](../../architecture/15-development-workflow.md#10-project-metrics--the-sloc-milestone-gate),
also report progress against the earlier **30,000 SLOC Project Health Review
reminder** the same way — and the first phase report to cross that threshold must
include the explicit reminder text SAD 15 §10 requires, not just the number.

## Complexity Metrics

- Cyclomatic Complexity (average, plus the grade distribution — e.g. how many
  functions fall into each radon-style A-F band — and name the highest-complexity
  outliers rather than only reporting the average)
- Average Function Length (lines)
- Average Class Size (lines)
- Largest Module (the package/service with the most total SLOC — distinct from
  Largest File)
- Largest File (the single largest source file, by line count)
- Number of Public APIs (business-domain endpoints, e.g. everything under a `/v1/...`
  prefix)
- Number of Internal APIs (operational endpoints, e.g. health/readiness/metrics under
  `/internal/...`)
- Number of Event Types (cross-reference against Architecture Metrics' event counts
  rather than recomputing independently)
- Number of Active Services (deployable services that exist — note explicitly if
  "active" means "defined" rather than "currently running," when no live environment
  is available to check)
- Number of Background Workers (separate worker processes/modules, distinct from the
  API service each belongs to)
