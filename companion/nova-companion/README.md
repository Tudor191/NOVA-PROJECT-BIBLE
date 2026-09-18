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
