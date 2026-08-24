# agents/research-agent

Research Agent (Bible Part 4, `category: research`) -- Phase 3's deliberately
minimal scope (TDD 3E §9): given `AgentContext.task.objective`, consults
`relevant_memory`/`relevant_knowledge` (already pre-scoped, doc 12 §4) and
calls `ai-model-orchestration-engine` (via `ModelGatewayPort`) to produce a
structured finding.

**Brought up and validated first, alone** -- proving the full Kernel
Scheduler -> Supervisor -> instance loop before the other four Phase 3 agents
(`coding-agent`, `qa-agent`, `architect-agent`, `documentation-agent`) exist
(roadmap step 4; see `docs/design/phase-3/08-tdd-3e-agent-os.md` §9, §13).

Not a uv/pnpm workspace member -- the Agent Registry's Phase 3 discovery is
filesystem-based (docs/architecture/12-agent-architecture.md §6, §15): it
reads `agent.yaml` and loads `src/handler.py` directly off disk, and
`agent-os/kernel`'s own `InprocessExecutionBackend` does the same at dispatch
time.

Has no peer-review role in Phase 3 (only `coding-agent`, reviewed by
`architect-agent`, does) and no `nova-auth` dependency (`required_permissions`
is declared-intent-only, per TDD 3E §5/§8a's own resolution).

## Testing

```bash
uv run pytest agents/research-agent/tests
```
