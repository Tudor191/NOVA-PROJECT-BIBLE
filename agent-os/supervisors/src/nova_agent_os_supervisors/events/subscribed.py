"""Every subject Supervisors is permitted to subscribe to.

Empty: serving the Supervisor's own inbox (`agent_os.instance.<this
instance's id>.inbox`, doc 12 §10) is Kernel's own inprocess execution
backend's job (doc 12 §8: `inprocess` runs an agent's asyncio task, and
by doc 12 §9's own "Supervisors are themselves agents" framing, that
includes a Supervisor instance) -- not yet built (`agent-os/kernel`'s own
`SUBSCRIBABLE_SUBJECTS` is equally empty as of this milestone). Disclosed,
matching `domain/ports.py`'s own "real code, no real caller/callee yet"
note."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(set())
