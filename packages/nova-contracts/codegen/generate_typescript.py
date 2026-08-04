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
    ConsolidationCompletedPayload,
    ConsolidationStartedPayload,
    DecisionRecordedPayload,
    EmbeddingCompletedPayload,
    EventEnvelope,
    HeartbeatPayload,
    KnowledgeLinkReplyPayload,
    KnowledgeLinkRequestPayload,
    KnowledgeTraverseReplyPayload,
    KnowledgeTraverseRequestPayload,
    LifecycleTransitionedPayload,
    LongTermMemoryCreatedPayload,
    LongTermMemoryUpdatedPayload,
    MemoryRetrieveReplyPayload,
    MemoryRetrieveRequestPayload,
    MemorySearchResultPayload,
    ModeChangedPayload,
    ModuleStatusChangedPayload,
    ShortTermMemoryCreatedPayload,
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

    index_lines = [f'export * from "./{name}";' for name in generated]
    (OUT_DIR / "index.ts").write_text("\n".join(index_lines) + "\n")

    shutil.rmtree(SCHEMA_DIR)
    print(f"Generated {len(generated)} TypeScript contract file(s) in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
