# agents/coding-agent

Coding Agent (Bible Part 4, `category: coding`) -- TDD 3E §9's exact Phase 3
scope: invokes `action-engine` (via `action.execute`, TDD 3D) using granted
`filesystem`/`terminal`/`git` capabilities to make a scripted code change.
"Scripted" here means deterministic and non-interpretive -- no LLM call, no
free-text parsing of the task objective for a target path -- the same
Phase-3-wide "no agent does open-ended, unscoped work" discipline
`research-agent`'s own README already establishes (TDD 3E §9, table footnote).
It writes one fixed-format record file per task, under a fixed
`coding-agent-output/<task-id>.md` project-relative path, via a `"write"`
`action.execute` filesystem operation, then **stages and commits it** —
three `action.execute` requests in order (decision D5):

| # | `action_type` | `execution_target` | operation |
|---|---|---|---|
| 1 | `filesystem` | `filesystem` | `write` the record file |
| 2 | `terminal` | `git` | `add` exactly that path |
| 3 | `terminal` | `git` | `commit -m "coding-agent: <objective>"` |

A completed task therefore leaves a **real commit** in the target
repository, not an uncommitted edit. Steps 2–3 carry `depends_on` pointing
at the previous step; `action-engine` records that field without gating on
it, and ordering is guaranteed by awaiting each step before the next.

**Exit codes are checked here.** A git command exiting non-zero is a
*successful invocation* to `capability-engine` and `action-engine` (TDD 3C
§8's structured failure), so the reply says `status="completed"` with
`result["exit_code"] != 0`. This agent inspects `exit_code` on both git
steps — the same convention `qa-agent` uses for `pytest` — and reports a
failed `AgentResult` naming the step, rather than a code change that never
landed. A failed step stops the chain: no commit is attempted after a
failed write or a failed stage.

**Target repository and environment.** Neither git step sends `repo_root`,
so `GitAdapter` uses its capability's declared root —
`Settings.sandbox_filesystem_root`, decision D7's target repository. The
subprocess environment is Slice 3's unchanged single `PATH`: `git add` and
`git commit` need no `HOME` (verified against real git), provided the target
repository has a **local** `user.name`/`user.email`, which D5 makes the
fixture's responsibility.

**Second Agent Package, second bring-up.** `research-agent` was brought up
and validated first, alone, proving the full Kernel Scheduler -> Supervisor
-> instance loop (roadmap step 4). This package is the first to actually
exercise the `AgentSDK`'s `action_port` and the first to carry a peer-review
pairing.

**Peer review.** `self_validate()` returns `requires_peer_review=True` on a
successful result -- TDD 3E §9's own `coding-agent`/`architect-agent`
pairing (doc 12 §9: "Coding Agent's output reviewed by an Architect agent
instance"). This package's own `agent.yaml` declares
`peer_reviewer_category: architect` (a disclosed addition to
`nova_agent_sdk.AgentManifest`, not part of doc 12 §3's worked example) so
the Kernel Scheduler can resolve a reviewer package for itself, with no new
Supervisor-side policy lookup needed for what is, in Phase 3, a single
static fact per agent category. See
`agent-os/kernel/src/nova_agent_os_kernel/domain/scheduler.py`'s own module
docstring for the full mechanism (`spawn_and_review()`, the
`agent_os.supervisor.peer_review.request` RPC, and the
Kernel-delivers/Supervisor-classifies ownership split).

**`architect-agent` does not exist yet.** This is a disclosed, intentional
sequencing gap (roadmap: `research-agent` -> `coding-agent` -> `qa-agent` ->
`architect-agent` -> `documentation-agent`), not a defect --
TDD 3E §9's own agent table gives `coding-agent`'s `execute()` scope no
dependency on `architect-agent`'s code, and TDD 3E §14's acceptance
criterion 1 (a real peer-review round) is the *final* Phase 3E gate, not a
per-agent build precondition. Until `architect-agent` is installed, every
peer-review round this package triggers resolves with
`reviewer_available=False` -> `peer_validation="timed_out"` -> the task
still finalizes as `outcome="success"` (TDD 3E §12's own non-fatal
treatment of a missing/unresponsive reviewer, extended to also cover "no
reviewer package installed yet" -- the concrete case this sequencing
produces). This package's own peer-review-triggering machinery
(`spawn_and_review()`, the new RPC, Decision Memory recording) is proven
end-to-end in `agent-os/kernel`'s and `agent-os/supervisors`' own test
suites using `research-agent`'s real on-disk Handler as a transport-only
stand-in reviewer (it has no reviewer-side logic either -- proves the
plumbing, not a reviewer verdict).

Not a uv/pnpm workspace member -- filesystem-based Agent Registry discovery,
identical to `research-agent`'s own precedent (see that package's own
README for the full disclosure).

Has no `nova-auth` dependency -- `required_permissions`/`required_capabilities`
are declared-intent-only in Phase 3 (TDD 3E §5/§8a's own resolution; Fork
3C-2's own resolution for capabilities), identical treatment to
`research-agent`'s own manifest.

## Testing

```bash
uv run pytest agents/coding-agent/tests
```
