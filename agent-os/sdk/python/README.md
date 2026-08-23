# nova-agent-sdk

The Agent SDK (docs/architecture/12-agent-architecture.md §4) -- the
standardized `AgentHandler` interface every Agent Package implements, plus
the `AgentManifest` (`agent.yaml`) schema the Registry validates against.

Every `agents/<name>-agent/src/handler.py` (doc 12 §3) implements
`AgentHandler` from this package:

```python
from nova_agent_sdk import AgentHandler, AgentManifest, AgentContext, AgentResult, ...

class Handler(AgentHandler):
    async def on_load(self, manifest: AgentManifest) -> None: ...
    ...
```

Independent of every engine's own domain implementation -- imports only
`nova_contracts` and `pydantic`.

## Testing

```bash
uv run --package nova-agent-sdk pytest
```
