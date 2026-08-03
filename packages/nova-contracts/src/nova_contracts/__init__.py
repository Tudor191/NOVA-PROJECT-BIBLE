"""nova-contracts: the single schema source of truth for NOVA.

Every event on the Event Bus and every cross-engine payload is defined exactly once
here (docs/architecture/02-repository-and-folder-structure.md §4). Python consumers
import these models directly; TypeScript consumers import the generated equivalents
under `typescript/` (see codegen/generate_typescript.py).
"""

from nova_contracts.envelope import EventEnvelope
from nova_contracts.events.system import (
    HeartbeatPayload,
    ModeChangedPayload,
    ModuleStatus,
    ModuleStatusChangedPayload,
    SystemMode,
)
from nova_contracts.registry import (
    known_subjects,
    payload_model_for,
    register_payload,
    validate_payload,
)

__all__ = [
    "EventEnvelope",
    "HeartbeatPayload",
    "ModeChangedPayload",
    "ModuleStatus",
    "ModuleStatusChangedPayload",
    "SystemMode",
    "known_subjects",
    "payload_model_for",
    "register_payload",
    "validate_payload",
]
