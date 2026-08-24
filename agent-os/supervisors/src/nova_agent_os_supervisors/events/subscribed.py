"""Every subject Supervisors is permitted to subscribe to.

`agent_os.supervisor.restart_plan.request` is the one addition, a disclosed
gap-closing RPC serving the Kernel Scheduler's own "owning Supervisor
applies its configured restart strategy" step (TDD 3E §12) -- see
`events/restart_plan_handler.py`'s own docstring. Serving the Supervisor's
own Agent Mailbox inbox (`agent_os.instance.<this instance's id>.inbox`,
doc 12 §10) remains Kernel's own inprocess execution backend's job and is
still not built here -- disclosed, matching `domain/ports.py`'s own "real
code, no real caller/callee yet" note for that specific gap."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "agent_os.supervisor.restart_plan.request",
    }
)
