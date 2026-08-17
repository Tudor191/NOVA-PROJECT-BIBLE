"""Concrete execution adapters -- real subprocess/filesystem/httpx I/O
(TDD 3C §3, Fork 3C-1/3D-1's resolution: this engine's own process is the
real executor for every adapter operation). Kept out of `domain/`
(docs/architecture/03-backend-architecture.md §1's framework-free
boundary) -- the same `connectors/` vs. `domain/` separation
`ai-model-orchestration-engine` already established.
"""
