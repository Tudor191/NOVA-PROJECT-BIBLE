# Build context is the repo root (docker build -f companion/nova-companion/Dockerfile .).
#
# The repository's first non-Python image. It follows every convention the
# Python images already established -- multi-stage, `apt` upgraded in the
# runtime stage, a non-root `nova` user at uid 1000, no build toolchain shipped
# -- and differs only where Rust genuinely differs.
#
# **The runtime base is `debian:trixie-slim`, not `rust:*`.** A Rust binary
# needs no toolchain at runtime, and shipping one would put a compiler and its
# whole dependency tree into a scanned image for nothing. `debian:trixie-slim`
# is the same Debian family `python:3.12-slim` is built on, so `apt-get upgrade`
# is the same hardening step and Trivy sees a familiar package database.
#
# `tools/tests/test_dockerfile_runtime_hardening.py` knows this base explicitly,
# by the ratified D-4F3-4: runtime families are enumerated there, and one
# without a hardening rule fails the guard rather than passing unnoticed.
FROM rust:1.94-slim-trixie AS builder
WORKDIR /build

# Manifests first, so a source-only change does not re-resolve the whole
# dependency graph. The same layering the Python images get from copying
# `pyproject.toml`/`uv.lock` ahead of the source.
COPY companion/Cargo.toml companion/Cargo.lock ./
COPY companion/nova-companion/Cargo.toml nova-companion/Cargo.toml
COPY companion/sensors/Cargo.toml sensors/Cargo.toml

COPY companion/nova-companion nova-companion
COPY companion/sensors sensors

RUN cargo build --release --locked --bin nova-companion

FROM debian:trixie-slim
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 nova
WORKDIR /app
COPY --from=builder --chown=nova:nova /build/target/release/nova-companion /app/nova-companion
USER nova

# **No EXPOSE, and no HEALTHCHECK.** The companion is a client, never a server
# (TDD 4F §7): it opens no listening port, so there is nothing to expose and
# nothing to probe over HTTP. A healthcheck here would have to invent a
# surface that the architecture forbids.

CMD ["/app/nova-companion"]
