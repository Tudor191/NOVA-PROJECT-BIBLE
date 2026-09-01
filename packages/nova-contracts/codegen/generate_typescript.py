#!/usr/bin/env python3
"""Generate TypeScript types from the Pydantic models that are NOVA's schema source
of truth. This is what keeps `typescript/` and `src/nova_contracts/` from drifting
apart (docs/architecture/02-repository-and-folder-structure.md §4).

Usage: uv run --package nova-contracts python codegen/generate_typescript.py
(invoked by `turbo run build --filter=@nova/nova-contracts` in CI, see
docs/architecture/17-cicd-pipeline.md).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from nova_contracts import (
    ActionApprovalDecidedPayload,
    ActionApprovalRequestedPayload,
    ActionExecuteRequestPayload,
    ActionResultPayload,
    AgentMessage,
    AgentOsFindHealthyPackageReplyPayload,
    AgentOsFindHealthyPackageRequestPayload,
    AgentOsPeerReviewReplyPayload,
    AgentOsPeerReviewRequestPayload,
    AgentOsRestartPlanReplyPayload,
    AgentOsRestartPlanRequestPayload,
    AgentOsTaskCompletedPayload,
    AttentionShiftedPayload,
    BudgetExceededPayload,
    CapabilityInvokeReplyPayload,
    CapabilityInvokeRequestPayload,
    CapabilityResolveReplyPayload,
    CapabilityResolveRequestPayload,
    CommunicationIntentDeliverReplyPayload,
    CommunicationIntentDeliverRequestPayload,
    CommunicationSessionCloseReplyPayload,
    CommunicationSessionCloseRequestPayload,
    CommunicationSessionCompletedPayload,
    CommunicationSessionCreatedPayload,
    CommunicationSessionCreateReplyPayload,
    CommunicationSessionCreateRequestPayload,
    CommunicationSessionLookupByUserReplyPayload,
    CommunicationSessionLookupByUserRequestPayload,
    CommunicationSessionStateChangedPayload,
    CommunicationTurnReceivedPayload,
    ConsolidationCompletedPayload,
    ConsolidationStartedPayload,
    ContextChangedPayload,
    ContextReplyPayload,
    ContextRequestPayload,
    ContradictionPayload,
    DecisionRecordedPayload,
    DigitalTwinPreferencesGetReplyPayload,
    DigitalTwinPreferencesGetRequestPayload,
    EmbeddingCompletedPayload,
    EmbedReplyPayload,
    EmbedRequestPayload,
    EventEnvelope,
    ExecutiveArbitrateReplyPayload,
    ExecutiveDecisionCompletedPayload,
    ExecutiveDecisionFailedPayload,
    ExecutiveHumanOverrideAppliedPayload,
    ExecutiveOutcomeReportPayload,
    ExecutiveOutcomeReportReplyPayload,
    ExecutiveRequestPayload,
    GenerateReplyPayload,
    GenerateRequestPayload,
    HeartbeatPayload,
    HumanOverrideAppliedPayload,
    KnowledgeEdgeCreatedPayload,
    KnowledgeLinkReplyPayload,
    KnowledgeLinkRequestPayload,
    KnowledgeNodeChangedPayload,
    KnowledgeRetrieveReplyPayload,
    KnowledgeRetrieveRequestPayload,
    KnowledgeSearchResultPayload,
    KnowledgeTraverseReplyPayload,
    KnowledgeTraverseRequestPayload,
    LayerAdvancedPayload,
    LifecycleTransitionedPayload,
    LongTermMemoryCreatedPayload,
    LongTermMemoryUpdatedPayload,
    MemoryRetrieveReplyPayload,
    MemoryRetrieveRequestPayload,
    MemorySearchResultPayload,
    ModeChangedPayload,
    ModelHealthChangedPayload,
    ModelRegistryChangedPayload,
    ModuleStatusChangedPayload,
    PersonalityMemoryUpdatePayload,
    PersonalityStyleSelectReplyPayload,
    PersonalityStyleSelectRequestPayload,
    PersonalityValidateResponseReplyPayload,
    PersonalityValidateResponseRequestPayload,
    PlanningDecomposeReplyPayload,
    PlanningDecomposeRequestPayload,
    PlanningGoalsCurrentReplyPayload,
    PlanningGoalsCurrentRequestPayload,
    PlanningTaskGraphCreatedPayload,
    PredictionPayload,
    ReasoningProcessCompletedPayload,
    ReasoningProcessFailedPayload,
    ReasoningReplyPayload,
    ReasoningRequestPayload,
    RequestCompletedPayload,
    RequestFailedPayload,
    ShortTermMemoryCreatedPayload,
    SynthesizeReplyPayload,
    SynthesizeRequestPayload,
    TranscribeReplyPayload,
    TranscribeRequestPayload,
    WorldObjectChangedPayload,
)
from pydantic import BaseModel

MODELS: list[type[BaseModel]] = [
    EventEnvelope,
    HeartbeatPayload,
    ModuleStatusChangedPayload,
    ModeChangedPayload,
    ShortTermMemoryCreatedPayload,
    LongTermMemoryCreatedPayload,
    LongTermMemoryUpdatedPayload,
    ConsolidationStartedPayload,
    ConsolidationCompletedPayload,
    LifecycleTransitionedPayload,
    DecisionRecordedPayload,
    EmbeddingCompletedPayload,
    MemorySearchResultPayload,
    MemoryRetrieveRequestPayload,
    MemoryRetrieveReplyPayload,
    KnowledgeLinkRequestPayload,
    KnowledgeLinkReplyPayload,
    KnowledgeTraverseRequestPayload,
    KnowledgeTraverseReplyPayload,
    KnowledgeNodeChangedPayload,
    KnowledgeEdgeCreatedPayload,
    ContradictionPayload,
    LayerAdvancedPayload,
    KnowledgeSearchResultPayload,
    KnowledgeRetrieveRequestPayload,
    KnowledgeRetrieveReplyPayload,
    WorldObjectChangedPayload,
    ContextChangedPayload,
    AttentionShiftedPayload,
    PredictionPayload,
    ContextRequestPayload,
    ContextReplyPayload,
    GenerateRequestPayload,
    GenerateReplyPayload,
    EmbedRequestPayload,
    EmbedReplyPayload,
    TranscribeRequestPayload,
    TranscribeReplyPayload,
    SynthesizeRequestPayload,
    SynthesizeReplyPayload,
    RequestCompletedPayload,
    RequestFailedPayload,
    ModelRegistryChangedPayload,
    ModelHealthChangedPayload,
    BudgetExceededPayload,
    ReasoningRequestPayload,
    ReasoningReplyPayload,
    ReasoningProcessCompletedPayload,
    ReasoningProcessFailedPayload,
    HumanOverrideAppliedPayload,
    ExecutiveRequestPayload,
    ExecutiveArbitrateReplyPayload,
    ExecutiveOutcomeReportPayload,
    ExecutiveOutcomeReportReplyPayload,
    ExecutiveDecisionCompletedPayload,
    ExecutiveDecisionFailedPayload,
    ExecutiveHumanOverrideAppliedPayload,
    PersonalityValidateResponseRequestPayload,
    PersonalityValidateResponseReplyPayload,
    PersonalityStyleSelectRequestPayload,
    PersonalityStyleSelectReplyPayload,
    PersonalityMemoryUpdatePayload,
    CommunicationSessionCreateRequestPayload,
    CommunicationSessionCreateReplyPayload,
    CommunicationSessionCloseRequestPayload,
    CommunicationSessionCloseReplyPayload,
    CommunicationIntentDeliverRequestPayload,
    CommunicationIntentDeliverReplyPayload,
    CommunicationSessionCreatedPayload,
    CommunicationSessionStateChangedPayload,
    CommunicationSessionCompletedPayload,
    CommunicationTurnReceivedPayload,
    CommunicationSessionLookupByUserRequestPayload,
    CommunicationSessionLookupByUserReplyPayload,
    DigitalTwinPreferencesGetRequestPayload,
    DigitalTwinPreferencesGetReplyPayload,
    CapabilityResolveRequestPayload,
    CapabilityResolveReplyPayload,
    CapabilityInvokeRequestPayload,
    CapabilityInvokeReplyPayload,
    ActionExecuteRequestPayload,
    ActionResultPayload,
    ActionApprovalRequestedPayload,
    ActionApprovalDecidedPayload,
    PlanningTaskGraphCreatedPayload,
    PlanningDecomposeRequestPayload,
    PlanningDecomposeReplyPayload,
    PlanningGoalsCurrentRequestPayload,
    PlanningGoalsCurrentReplyPayload,
    AgentMessage,
    AgentOsTaskCompletedPayload,
    AgentOsFindHealthyPackageRequestPayload,
    AgentOsFindHealthyPackageReplyPayload,
    AgentOsPeerReviewRequestPayload,
    AgentOsPeerReviewReplyPayload,
    AgentOsRestartPlanRequestPayload,
    AgentOsRestartPlanReplyPayload,
]

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = PACKAGE_ROOT / "codegen" / ".schemas"
OUT_DIR = PACKAGE_ROOT / "typescript"


def _json2ts_command() -> list[str]:
    """Resolve a runnable `json2ts` command from the package-local node_modules."""
    local_bin = PACKAGE_ROOT / "node_modules" / ".bin" / "json2ts"
    if local_bin.exists():
        return [str(local_bin)]
    pnpm = shutil.which("pnpm")
    if pnpm:
        return [pnpm, "--dir", str(PACKAGE_ROOT), "exec", "json2ts"]
    raise RuntimeError(
        "json-schema-to-typescript is not installed. Run `pnpm install` at the repo "
        "root first (it is a devDependency of @nova/nova-contracts)."
    )


def main() -> int:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json2ts = _json2ts_command()

    generated: list[str] = []
    for model in MODELS:
        schema = model.model_json_schema()
        schema["title"] = model.__name__
        schema_path = SCHEMA_DIR / f"{model.__name__}.schema.json"
        schema_path.write_text(json.dumps(schema, indent=2))

        out_path = OUT_DIR / f"{model.__name__}.ts"
        result = subprocess.run(
            [*json2ts, str(schema_path), "-o", str(out_path), "--bannerComment", ""],
            cwd=PACKAGE_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            return result.returncode
        generated.append(model.__name__)

    # Re-export each payload interface by name rather than with `export *`.
    # `json2ts` emits a scalar alias per property alongside the root interface, so
    # nearly every module also exports `SchemaVersion` (94 of 97), `CorrelationId`
    # (31), `UserId` (25) and so on. A barrel of `export *` lines therefore collides
    # on those incidental names -- 395 `TS2308` errors, which went unnoticed because
    # nothing had ever type-checked this output. The model names are unique, so
    # named re-exports are unambiguous. Consumers that need a property alias import
    # it from the module that owns it, which is correct anyway: `SchemaVersion` in
    # `HeartbeatPayload` and in `ActionResultPayload` are unrelated types that merely
    # share a name.
    index_lines = [f'export type {{ {name} }} from "./{name}";' for name in generated]
    (OUT_DIR / "index.ts").write_text("\n".join(index_lines) + "\n")

    shutil.rmtree(SCHEMA_DIR)
    print(f"Generated {len(generated)} TypeScript contract file(s) in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
