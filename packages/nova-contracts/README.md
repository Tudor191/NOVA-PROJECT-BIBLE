# nova-contracts

The single schema source of truth for NOVA (docs/architecture/02 §4).

- `src/nova_contracts/envelope.py` — `EventEnvelope`, the common wire format for
  every event on the Event Bus.
- `src/nova_contracts/registry.py` — the payload schema registry
  (`@register_payload`, `validate_payload`) engines use to declare and validate what
  they publish.
- `src/nova_contracts/events/` — one module per event family (e.g. `system.py` for
  `nova.*` events owned by `nova-core`). Add a new module here whenever an engine
  gains a new published event family.
- `typescript/` — generated TypeScript types, produced by `codegen/generate_typescript.py`.
  **Do not hand-edit** — regenerate via `pnpm turbo run build --filter=@nova/nova-contracts`.

## Adding a new event

1. Add the Pydantic payload model to the relevant file under `src/nova_contracts/events/`
   (or create a new file for a new event family).
2. Decorate it with `@register_payload("your.subject.here")`.
3. Export it from `src/nova_contracts/__init__.py`.
4. Add it to `MODELS` in `codegen/generate_typescript.py` so the TypeScript side stays
   in sync.
5. Run `pnpm turbo run build --filter=@nova/nova-contracts` to regenerate `typescript/`.
