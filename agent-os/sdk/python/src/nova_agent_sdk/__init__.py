"""nova-agent-sdk -- the Agent SDK (doc 12 §4): the standardized
`AgentHandler` interface every Agent Package implements, plus the
`AgentManifest` (`agent.yaml`) schema the Registry validates against.

`AgentContext`/`AgentHealth`/`AgentMetrics`/`AgentResult`/`AgentMessage`/
`ValidationOutcome` are re-exported from `nova_contracts` (already defined
there, Phase 3E Milestone 1) so an Agent Package author needs only one
import line -- mirrors `nova_action_engine.domain.models`'s own
re-export-from-`nova_contracts` convention.

Independent of every engine's own domain implementation by construction:
this package imports only `nova_contracts` and `pydantic`, never an
engine's own top-level package (enforced by the
`nova-agent-sdk has no engine-specific knowledge` import-linter contract).
"""

from nova_contracts import (
    AgentContext,
    AgentHealth,
    AgentMessage,
    AgentMetrics,
    AgentResult,
    ValidationOutcome,
)

from nova_agent_sdk.handler import AgentHandler
from nova_agent_sdk.manifest import (
    AgentManifest,
    CompatibilityInfo,
    HealthCheckConfig,
    ResourceProfile,
)

__all__ = [
    "AgentContext",
    "AgentHandler",
    "AgentHealth",
    "AgentManifest",
    "AgentMessage",
    "AgentMetrics",
    "AgentResult",
    "CompatibilityInfo",
    "HealthCheckConfig",
    "ResourceProfile",
    "ValidationOutcome",
]
