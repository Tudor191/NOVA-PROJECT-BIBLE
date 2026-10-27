# nova-companion

**The Rust OS-level perception daemon** — doc 02's `companion/` tree, TDD 4F §7,
built in slice **4F.3**.

One job: watch **one explicitly configured directory** and submit each real
filesystem change to `perception-engine`'s existing intake route.

## What it is not

Every line here is a boundary, not a to-do list.

| | |
|---|---|
| **A server** | No listening port. It is a client; there is no HTTP server dependency in `Cargo.toml`, so this is structural rather than conventional |
| **An Event Bus participant** | It never connects to NATS and has no client to do so |
| **A store owner** | No persistence of any kind |
| **An actuator** | 4F.3 implements none. TDD 4F §7.3 puts terminal and window control behind `action-engine` action types when they arrive |
| **A hashing authority** | `perception-engine` hashes the path (**D-4F3-2**). A second implementation here would put the handle format in two languages, where a divergence produces duplicate world objects rather than a loud failure |
| **An engine** | ADR-004's engine-to-engine prohibition is not engaged, because one side is not an engine |

## The sensor split (D-4F3-1)

"The filesystem sensor" is two objects in two languages, deliberately:

| | This crate | `perception-engine` |
|---|---|---|
| Language | Rust | Python |
| Job | Watch a directory, emit observations, POST them | Satisfy the `Sensor` Protocol so the route's lookup and lifecycle gate work |
| Knows about | The filesystem, one HTTP endpoint | Nothing about the filesystem |

The Python half exists because the intake route resolves
`sensors_by_source["filesystem"]` and gates on `state() != "running"`. That gate
is what makes AC-7 clause 2's revocation real: pausing the registry entry makes
the engine drop observations whatever this process is still doing.

## Configuration

Environment only, `NOVA_COMPANION_` prefixed, matching every engine's
`pydantic-settings` convention.

| Variable | Required | Default |
|---|---|---|
| `NOVA_COMPANION_WATCH_ROOT` | **Yes** | **None, deliberately** |
| `NOVA_COMPANION_PERCEPTION_BASE_URL` | **Yes** | None |
| `NOVA_COMPANION_SOURCE` | No | `filesystem` |
| `NOVA_COMPANION_REQUEST_TIMEOUT_MS` | No | `5000` |

**`WATCH_ROOT` has no default and never will.** A fallback to the current
directory or `$HOME` would be a privacy decision made by a default value, which
**D-4F3-3** forbids. Startup fails loudly instead.

## Consent — a policy boundary, not a mechanism

**D-4F3-3, stated plainly: 4F.3 adds no consent subsystem, and this component
does not enforce filesystem consent.** There is no consent API, no consent
database and no policy engine here.

Doc 22 Principle 8's per-source consent requirement for the filesystem source
remains an **open policy question**, carried as ledger row **L-14**. What bounds
the risk meanwhile is the scope rule above: one configured directory, never the
whole filesystem, and no code path that can widen it.

## A lost permission — Phase 4F.8

*(A-4F8-1 (a), (a1) and (a2), ratified 2026-10-11; TDD 4F.8 §29.1.)*

This process is the only one that holds the OS permission on the watched
directory, so it is the one that detects losing it.

- **Detection.** After a `chmod` on the root, an existing inotify watch keeps
  delivering events, but nothing inside the root can be read (F-4F8-7,
  F-4F8-15). Until 4F.8 those events were dropped with nothing said. Now the
  root's read and search permission are re-checked:
  - on every metadata change of the root itself, which is how a `chmod` arrives
    (`IN_ATTRIB`);
  - before every observation is emitted, and again before every submission.
- **The report.** A denial is logged once, as `permission_revoked`, and reported
  on `POST /v1/perception/permission-revocations?source=<source>` with body
  `{"detected_at": "<RFC3339>"}`. The body carries no path and no identity.
  - It is the one route A-4F8-1 (a1) ratified, on the same internal surface.
  - The workspace-observation contract is unchanged.
  - An unacknowledged report is sent again on the next event, with no timer.
  - `perception-engine` moves its sensor to `failed`. That is its decision,
    because it owns the lifecycle.
- **After it.** **Nothing is submitted again for the rest of the process's
  life**, even if the permission comes back. Recovery needs a restart of this
  process and the engine: (a2)'s disclosed limitation.
- **Never:** an inference from silence, or an exit because of the loss.
- **Only a permission failure counts.** A root that vanished, or another I/O
  failure, is not reported as a revocation.

The tests that prove it change a real directory's real mode bits:
`sensors/tests/revocation.rs` and `nova-companion/tests/revocation.rs`. They
**must run as a non-root user**, because root bypasses permission checks. They
fail loudly, rather than pass vacuously, if the OS does not deny access. CI runs
`cargo test` as the runner's unprivileged user.

## What travels, and what does not

The companion sends the **real path** to the engine over the internal Docker
network. The requirement **D-4F3-2** states is about outputs, not the wire:

> The raw path must not be present in the persisted payload, the outbox row, the
> published event, or any downstream world-model data.

Those are all on the engine's side, and the engine's own tests assert it.

**Logs carry a file name, never a directory chain.** The one exception is a
startup configuration error, which names the operator's own misconfigured value
so they can fix it.

## `observed_at`

The **file's own modification time**, read from the filesystem — not the moment
this process noticed the change. `notify` supplies no timestamp, and TDD 4F
§20.1 forbids fabricating one, so an event whose mtime cannot be read is
**dropped rather than stamped with the current clock**.

**This slice does not measure AC-7.** It supplies the genuine OS event that
starts AC-7's interval for the first time; measuring that interval honestly is
4F.8's work.

## Running the tests

```bash
cd companion
cargo fmt --all --check
cargo clippy --all-targets --locked -- -D warnings
cargo test --all-targets --locked
```

The same three commands CI runs. `companion/` is a Cargo workspace and is
neither a pnpm nor a `uv` workspace member, so Turborepo never sees it — the
same reason `tools/tests` and the Agent Packages run as their own CI steps.

**The filesystem tests use a real temp directory and real file operations.** No
event is constructed and injected: S-1 requires that detection itself be
exercised.

## Image

`debian:trixie-slim` at runtime, not `rust:*` — a Rust binary needs no toolchain
at runtime, and shipping one would put a compiler into a scanned image for
nothing. It is in the `build-and-scan` matrix and **Trivy-scanned like every
other image**; `tools/tests/test_dockerfile_runtime_hardening.py` knows this
runtime base explicitly (**D-4F3-4**), and a new runtime family added without a
hardening rule fails that guard rather than passing unnoticed.
