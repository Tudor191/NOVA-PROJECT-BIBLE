# `@nova/ui`

The shared design-system package named in
[doc 04 §6](../../docs/architecture/04-frontend-architecture.md). Built in
**Phase 4A**, deliberately minimal: a finished design system is an explicit
4A non-goal ([TDD 4A](../../docs/design/phase-4/01-tdd-4a-gateways-and-web-client.md)
§13). What ships here is only what the application shell and the Conversation
panel need.

## What belongs in this package

A component earns a place here when it carries a **rule**, not just a look.
Every component below exists because some architectural constraint has to be
true at the last mile, where a person actually reads the screen:

| Component | The rule it holds |
|---|---|
| `ConfidenceBadge` | A confidence that was never reported renders as *"no confidence reported"* — never as 0%, never hidden. Part 8's Confidence System only means something if an absent signal is distinguishable from a low one. |
| `ConfidenceTierBadge` | `communication.intent.delivered` reports a tier *word*. Nothing on that path converts it to a number, and neither does this — a percentage here would be a value invented at the last possible moment. |
| `StatusDot` | Animates only when a caller holding a real signal asks it to, one shot per signal. Doc 04 §4 and Bible Part 6: *never generate fake animations.* `unknown` is a first-class state, not a rendering of `down`. |
| `DegradationNotice` | *Never silence, always disclose degradation.* An unreachable engine, an expired session, a rate limit and a contract mismatch all surface here rather than as an empty panel. |
| `CorrelationTag` | The envelope is rendered, not hidden (TDD 4A §5.2). The id that links what the user sees to the event chain that produced it stays on screen and stays copyable. |
| `Panel`, `Button`, `TextField` | Plain primitives. `TextField` forwards its ref because React Hook Form registers inputs that way (doc 04 §5). |

## Consuming it

Source-only — no build step. `apps/web-client` imports the components
directly and the stylesheet once:

```ts
import { Panel, ConfidenceBadge } from "@nova/ui";
import "@nova/ui/styles.css";
```

The styles are plain CSS over custom properties rather than Tailwind
`@apply`, so this package has no coupling to the consumer's Tailwind version
while the app still uses Tailwind utilities for layout.

## Checks

```
pnpm --filter @nova/ui run test       # vitest + Testing Library, jsdom
pnpm --filter @nova/ui run typecheck  # tsc --noEmit, strict
pnpm --filter @nova/ui run lint       # eslint (the TS analogue of ruff)
```

All three also run repo-wide via `pnpm turbo run <task>`, which is what CI
invokes.
