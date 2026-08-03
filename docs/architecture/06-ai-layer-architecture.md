# 06 — AI Layer Architecture

The AI layer is the composition of three engines (per ADR-002): **AI Model
Orchestration Engine**, **Reasoning Engine**, and **Planning Engine**, coordinated by
**Executive Cognition Engine**. This document describes them as one layer because the
Bible's "AI Core" (Part 2) is exactly their combined behavior.

## 1. Model Gateway (`ai-model-orchestration-engine`)

```
services/ai-model-orchestration-engine/src/nova_ai_model_orchestration_engine/
├── domain/
│   ├── router.py                # Model selection algorithm
│   ├── capability_matrix.py     # Per-model capability scores (Part 7)
│   ├── cost_tracker.py
│   └── privacy_classifier.py    # Part 7 "Privacy Management": public/internal/confidential/highly-sensitive
├── connectors/
│   ├── base.py                  # ModelConnector protocol: generate/embed/stream/tool_call
│   ├── ollama_connector.py      # Default, always present
│   ├── anthropic_connector.py
│   ├── openai_connector.py
│   ├── google_connector.py
│   └── ...                      # one file per provider; adding a provider = adding one file
└── registry/
    └── model_registry.py        # Persisted in Postgres: name, version, provider, capabilities,
                                  # context window, latency, cost, health
```

### Routing algorithm (Part 7's "Orchestration Principle", concretely)

```mermaid
flowchart TD
    A[Request: task + context] --> B[Classify task type & complexity]
    B --> C[Classify privacy level]
    C --> D{Highly sensitive?}
    D -- yes --> E[Restrict to local connectors only]
    D -- no --> F[Query Capability Matrix for candidate models]
    E --> F
    F --> G[Score candidates: capability x historical success / (latency, cost)]
    G --> H[Select top model + 1 fallback]
    H --> I[Execute via connector]
    I --> J{Success & confidence >= threshold?}
    J -- no --> K[Fallback model / reduce context / retry]
    J -- yes --> L[Record outcome -> update routing weights]
```

This directly implements Part 7's "Model Learning" ("learn which model solves which
tasks better... routing becomes increasingly intelligent") as an online-updated
weighting, not a static config.

### Zero-budget default

Out of the box (`infra/docker/docker-compose.local.yml`), only the Ollama connector is
enabled, pointed at locally pulled models (Llama, Qwen, Mistral, DeepSeek, Gemma, Phi
per Part 7). Cloud connectors activate the moment a user supplies an API key through
the Command Center's AI Control Center panel — no redeploy required (hot-reloadable
registry entry).

## 2. Reasoning Engine

Implements Part 8's four **Reasoning Levels** as an explicit, inspectable pipeline
stage rather than a prompt convention:

| Level | Trigger | Pipeline depth |
|---|---|---|
| 1 — Instant | Simple factual/deterministic queries | Single model call, no hypothesis generation |
| 2 — Analytical | Programming, research, writing, debugging | Hypothesis generation + evidence collection + single-pass evaluation |
| 3 — Strategic | Architecture, business planning, system design | Multiple alternatives (Decision Matrix, Part 8) + risk estimation + confidence scoring |
| 4 — Deep | Multi-day/enterprise-scale problems | Full pipeline + multi-agent peer review (delegates to Agent Orchestrator) + failure simulation |

The `domain/pipeline.py` module implements the fixed 13-step sequence from Part 8
verbatim (receive objective → understand intent → load memories → load World Model →
retrieve knowledge → generate hypotheses → evaluate alternatives → estimate risks →
predict outcomes → choose strategy → validate internally → execute → review/learn) as
a state machine, with each step emitting a `reasoning.step.completed` event so the
frontend's Reasoning panel can render it live (Part 8 "Reasoning Visualization" —
"never generate fake animations" applies here too: the visualization *is* the state
machine's actual transitions).

Confidence output (Part 8 "Confidence Estimation") is a first-class field on every
`reasoning.result` event: `{value: float, tier: "verified"|"likely"|"needs_validation"|"insufficient", evidence: [...]}`,
consumed downstream by Autonomy Engine's Confidence Gating (Part 14) and by
Communication Engine to decide how hedged the final response should sound (Part 17
"Confidence Expression").

## 3. Planning Engine

Converts a Reasoning Engine output into a **Task Graph** — the concrete data structure
behind Part 2's "Internal Task Graph" and Part 9's Work Breakdown Structure:

```python
class TaskNode(BaseModel):
    id: UUID
    objective: str
    depends_on: list[UUID]
    assigned_agent_category: str | None   # e.g. "coding-agent"
    estimated_effort: Estimate
    risk: RiskLevel
    status: Literal["pending","ready","running","blocked","completed","failed"]

class TaskGraph(BaseModel):
    id: UUID
    root_objective: str
    nodes: list[TaskNode]
    critical_path: list[UUID]             # Part 9 "Critical Path Analysis"
```

Independent nodes (no shared `depends_on` edges) are dispatched to the Agent
Orchestrator in parallel (Part 2 "Internal Task Graph": "independent nodes should
execute simultaneously"). The graph is persisted (Postgres) so long-running plans
survive process restarts and support **Dynamic Replanning** (Part 9) by mutation
rather than regeneration from scratch.

## 4. Prompt orchestration

Per Part 7 "Prompt Orchestration," every model call is assembled from named,
independently-testable components rather than a single hand-written string:

```
PromptAssembly
├── system_identity        (from Personality Engine)
├── current_goal           (from Executive Cognition Engine)
├── world_model_context    (from World Model Engine, scoped per Part 11 "Agent Awareness")
├── relevant_memory        (from Memory Engine retrieval)
├── knowledge_retrieval    (from Knowledge Engine)
├── available_capabilities (from Capability Engine, scoped to the task)
├── user_request
└── execution_constraints  (policies, autonomy level, risk tolerance)
```

Each component is fetched via its owning engine's API/event, cached per-request, and
unit-testable in isolation — this is what keeps context "quality over size" (Part 7)
enforceable: each component has its own token budget and truncation/summarization
strategy rather than one global prompt-stuffing routine.

## 5. Executive Cognition Engine — coordination layer

`executive-cognition-engine` does not reason or plan itself; it owns **attention
allocation, goal hierarchy, and conflict resolution across the other AI-layer engines**
(Part 19). Concretely, it is the subscriber that decides, when Reasoning Engine,
Planning Engine, and Autonomy Engine simultaneously want cognitive/GPU resources, whose
request proceeds first — implemented as a priority queue keyed on the Cognitive
Priority Matrix (urgency × importance × risk × learning value × resource cost, Part 6).

## 6. Independence from any single provider (verification)

Every connector, every prompt component, and every engine in this layer depends only on
the `ModelConnector` protocol and `nova-contracts` types — never on a provider SDK
directly outside `connectors/*_connector.py`. A CI contract test (`test_connector_swap.py`)
runs the entire Reasoning Engine test suite against a fake local connector to prove this
boundary holds, satisfying every engine's repeated "must remain independent from any
individual language model" requirement as an executable, not just a paper, guarantee.
