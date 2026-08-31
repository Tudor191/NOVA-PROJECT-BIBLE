# agents/architect-agent

Architect Agent (Bible Part 4, `category: architect`) -- TDD 3E §9's exact
Phase 3 scope: the scripted peer-review reviewer -- consumes `coding-agent`'s
`AgentResult` via `PEER_REVIEW_REQUEST`, produces a structured review
verdict.

**Fourth Agent Package, and the first to be a pure reviewer.** Unlike
`research-agent`/`coding-agent`/`qa-agent`, this package's real Phase 3 work
happens in `on_message()`, not `execute()` -- TDD 3E §9's own agent table
gives `architect-agent` no task-assignment behavior. `execute()` is still
implemented (a deterministic, disclosed stub) to satisfy `AgentHandler`'s
full Protocol shape, but no Phase 3 Task Graph node is ever assigned
`category="architect"`.

**Closes the peer-review loop `coding-agent`'s own slice opened.** Since
`coding-agent` shipped, every peer-review round it triggers has resolved to
`reviewer_available=False` -> `peer_validation="timed_out"` (no
`architect-agent` package installed). Installing this package is what makes
`agent-os/kernel`'s existing `spawn_and_review()` mechanism -- already
implemented, unchanged by this slice -- actually reach a real reviewer:
`coding-agent`'s own manifest already declares
`peer_reviewer_category: architect`, and the Kernel Scheduler resolves this
package by that exact category via the existing `RegistryPort`.

**No new mailbox, persistence layer, or peer-review protocol.** This
package is purely the reviewer-side implementation of the already-approved
mechanism: `agent-os/kernel`'s Scheduler still owns reviewer discovery and
delivers `PEER_REVIEW_REQUEST` via `InprocessExecutionBackend.spawn_and_review()`
(constructs this Handler, drives `on_load -> on_message -> on_unload`);
`agent-os/supervisors` still owns classification
(`classify_reviewer_result()`) and Decision Memory recording via the
existing `agent_os.supervisor.peer_review.request` RPC. See
`agent-os/kernel/src/nova_agent_os_kernel/domain/scheduler.py`'s and
`domain/execution_backend.py`'s own module docstrings for the full,
unchanged mechanism.

**"Scripted review verdict," disclosed.** Like every other Phase 3 agent
(TDD 3E §9's own "no agent does open-ended, unscoped work" principle), the
review is a deterministic, non-interpretive check -- no LLM call, no static
analysis, no free-form code-quality judgment. It approves iff the primary
result's own self-report is internally consistent
(`status == "success"` and `self_validation_passed is True`); anything else
is rejected (`AgentResult.status="needs_revision"`). A genuine code-quality
reviewer (deeper static analysis, a model call) is out of Phase 3's scope
entirely -- flagged for future refinement, the same disclosure discipline
`action-engine`'s own `domain/risk.py::classify_risk` already establishes.

Not a uv/pnpm workspace member -- filesystem-based Agent Registry discovery,
identical to every other Agent Package's own precedent.

Has no `nova-auth` dependency -- `required_permissions`/`required_capabilities`
are both empty (this package calls neither `action-engine` nor
`capability-engine` at all) and declared-intent-only in Phase 3 regardless
(TDD 3E §5/§8a's own resolution), identical treatment to the other three
Agent Packages' own manifests.

## Testing

```bash
uv run pytest agents/architect-agent/tests
```
