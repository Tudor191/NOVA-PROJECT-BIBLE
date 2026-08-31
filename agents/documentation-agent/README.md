# agents/documentation-agent

Documentation Agent (Bible Part 4, `category: documentation`) -- TDD 3E §9's
exact Phase 3 scope: calls `ai-model-orchestration-engine` to produce
documentation content, writes it via `action-engine`'s `filesystem`
capability.

**Fifth and final Phase 3E Agent Package.** The first (and only) Phase 3
agent to use both `ModelGatewayPort` (`research-agent`'s own precedent) and
`ActionPort` (`coding-agent`'s own precedent) for real in the same
`execute()`: TDD 3E §9's own sentence names both steps explicitly --
generate content, then write it. No new mechanism -- this is a direct
composition of two already-approved, already-used ports; see
`src/handler.py`'s own docstring for the full disclosure.

**"Scripted," disclosed.** Like every other Phase 3 agent (TDD 3E §9's own
"no agent does open-ended, unscoped work" table footnote), only the task's
own `objective` varies the content produced -- the instruction itself is a
fixed constant, and the write target is a fixed, deterministic
`documentation-agent-output/<task-id>.md` path, never derived from
free-text parsing of the objective.

**No peer-review role, no interaction with other agents.** TDD 3E §9's own
agent table gives `documentation-agent` no `peer_reviewer_category` -- only
`coding-agent`, reviewed by `architect-agent`, has one -- and describes no
Agent-Mailbox interaction with any other agent. `self_validate()` returns
`requires_peer_review=False` unconditionally.

Not a uv/pnpm workspace member -- filesystem-based Agent Registry discovery,
identical to every other Agent Package's own precedent.

Has no `nova-auth` dependency -- `required_permissions`/`required_capabilities`
are declared-intent-only in Phase 3 (TDD 3E §5/§8a's own resolution; Fork
3C-2's own resolution for capabilities), identical treatment to the other
four Agent Packages' own manifests. `required_capabilities` lists only
`filesystem` -- `ai-model-orchestration-engine` is called directly via
`model_gateway`, not through a capability-engine adapter, mirroring
`research-agent`'s own manifest.

## Testing

```bash
uv run pytest agents/documentation-agent/tests
```
