# agents/qa-agent

QA Agent (Bible Part 4, `category: qa`) -- TDD 3E §9's exact Phase 3 scope:
invokes `action-engine`'s `terminal` capability to run a test suite;
`AgentResult.status` reflects pass/fail directly, not interpreted. "Not
interpreted" means: `action-engine`'s own `terminal` adapter runs the
subprocess and reports `status="completed"` even when the test suite itself
fails (a nonzero exit code is the suite's own verdict, not an action
failure) -- this Handler reads `result["exit_code"]` directly (`0` -> pass,
anything else -> fail) rather than parsing `stdout`/`stderr` content or
applying any heuristic. The command itself is fixed and scripted
(`pytest -q`), never derived from free-text parsing of the task objective --
the same Phase-3-wide "no agent does open-ended, unscoped work" discipline
`research-agent`'s and `coding-agent`'s own READMEs already establish.

**Third Agent Package.** `research-agent` (no peer review) and `coding-agent`
(reviewed by `architect-agent`) were brought up first, in that order,
proving first the full Kernel Scheduler -> Supervisor -> instance loop and
then the peer-review orchestration mechanism.

**No peer-review role, no direct Coding/Architect Agent interaction.**
TDD 3E §9's own agent table gives `qa-agent` no `peer_reviewer_category` --
only `coding-agent`'s manifest declares one, reviewed by `architect-agent`.
`qa-agent` is neither a reviewer nor a reviewee in Phase 3, and its
`self_validate()` returns `requires_peer_review=False` unconditionally
(mirrors `research-agent`'s own precedent). This is a deliberate narrowing
of doc 12 §9's own broader, aspirational Part-4 framing ("Coding Agent's
output reviewed by an Architect agent instance **and a QA agent
instance**") to TDD 3E §9's actual Phase-3 text, which assigns the peer
reviewer role to `architect-agent` alone. Any relationship between a
`qa-agent` task and a `coding-agent` task (e.g. "run the tests after the
code change") is expressed the same way any two dependent Task Graph nodes
are -- `TaskNodeSnapshot.depends_on`, `planning-engine`'s own pre-existing
mechanism (TDD 3B) -- never a new Agent Mailbox message type or a second
peer-review round. This package's own `Handler` has no reference to
`coding-agent` or `architect-agent` at all.

Not a uv/pnpm workspace member -- filesystem-based Agent Registry discovery,
identical to `research-agent`'s and `coding-agent`'s own precedent.

Has no `nova-auth` dependency -- `required_permissions`/`required_capabilities`
are declared-intent-only in Phase 3 (TDD 3E §5/§8a's own resolution; Fork
3C-2's own resolution for capabilities), identical treatment to the other
two Agent Packages' own manifests.

## Testing

```bash
uv run pytest agents/qa-agent/tests
```
