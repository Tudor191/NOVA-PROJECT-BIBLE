"""Every subject Cognitive State Engine is permitted to subscribe to.

**Exactly one, since Phase 4F.7: `perception.sensor.health_changed`** -- TDD 4F
§24.4 **RS-3a** and TDD 4F.7 §8.2. It is an **existing**, registered subject
(`PerceptionSensorHealthChangedPayload`), published by `perception-engine` on
its sensor lifecycle transitions. This engine consumes it as an **internal
input** to its read surface: it stores the latest normalized state per sensor
(`cognitive_state.sensor_state`) and serves it under `/v1/cognitive-state`.

**No subject is authored here, and none is added.** The subject has been in
`ws-gateway`'s `PUBLIC_TOPICS` since 4B, so browsers can also receive it --
RS-3a records that as an accepted consequence. Subscribing here changes neither
the contract nor `PUBLIC_TOPICS`.

**Not for thought ingestion.** Creating Active Thoughts from Event Bus inputs is
the promotion slice 4F.P's (RS-1c, RS-2b); this subscription feeds sensor state
only.

*(Until 4F.7 this set was empty, and this docstring read: "**Empty in 4F.1.**
TDD 4F §13 records that this engine consumes perception observations and World
Model context *"via the Event Bus only"* -- but 4F.1 is the domain and
persistence slice, and it has no handler to route a subject to. ... Subjects
arrive with the handlers that consume them, in **4F.6**, and every one of them
already exists -- this engine will be a new *consumer* of existing contracts,
never the author of a new one (D-4D-1)." 4F.6 added no subscription: its trigger
condition is a promotion, not an inbound event. The last clause still holds.
Preserved per protocol §0.3.4.)*
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset({"perception.sensor.health_changed"})
