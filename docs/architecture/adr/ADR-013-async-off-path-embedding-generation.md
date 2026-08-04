# ADR-013 — Asynchronous, off-write-path embedding generation

**Subsystem:** Memory Engine, Knowledge Engine
**Status:** Accepted, implemented

## Context

Both Memory Engine and Knowledge Engine need vector embeddings (via the
`EmbeddingProvider` interface, ADR-009, backed by Ollama's `nomic-embed-text` per
ADR-010) for every long-term memory and every knowledge node, to support semantic
search. Ollama embedding calls are local-model inference — slower and more
variable in latency than a database write.

## Problem

Should embedding generation happen synchronously, as part of the write request
that creates a memory or knowledge node, or asynchronously, decoupled from that
write?

## Alternatives considered

- **Synchronous embedding on write.** Rejected: a caller creating a memory or
  knowledge node would have its request latency dominated by Ollama inference
  time, not by the actual database write — the two have no reason to be coupled
  from the caller's perspective, and Part 3/Part 10 both describe memory/knowledge
  creation as something that should feel immediate (e.g., a decision gets recorded
  the moment it's made, not after a model call completes).
- **Synchronous embedding with a request timeout and fallback to unembedded.**
  Rejected as unnecessarily complex: this reintroduces most of the async
  worker's machinery (a retry path for the fallback case) while still coupling
  the common-case write latency to inference time.

## Decision

A memory or knowledge node is written with `embedding = NULL`. A separate Arq
worker (`embedding_worker.py` in both engines) polls for unembedded rows,
generates embeddings in batches via `EmbeddingProvider.embed_batch`, and fills the
column off the write path entirely. Semantic search queries filter out rows with
`embedding IS NULL` (or, per each engine's retrieval design, degrade gracefully by
falling back to non-semantic search components for those rows).

## Consequences

- Write latency for a memory or knowledge node is bounded by the database write
  alone, never by embedding inference time.
- A newly created memory/node is briefly unsearchable by semantic similarity
  (until the next worker pass) but is immediately searchable by every other
  retrieval path (timeline, graph, name-based) — an accepted, bounded staleness
  window, not a correctness gap.
- Both engines' `embedding_worker.py` follow an identical mechanism, making this a
  reusable pattern rather than two independent designs that happen to converge.

## Tradeoffs

- A memory/node created and immediately searched semantically (within the worker's
  poll interval) will not appear in semantic search results yet. Acceptable
  because Phase 1 has no real-time "search what I just said" requirement that
  demands sub-second embedding availability; would need revisiting if such a
  requirement emerges.
- The embedding worker introduces a second process each engine must run and
  monitor (`embeddings_total` counter exists in both engines' observability for
  exactly this reason — an unembedded backlog should be visible, not silent).

## Future implications

If a future requirement needs embeddings available synchronously (e.g., a
capability that must semantically search a record the instant it's created), the
correct fix is a targeted synchronous path for that specific capability, not
converting the general write path back to synchronous embedding — the general
case's latency guarantee should not regress to serve one caller's stricter need.
