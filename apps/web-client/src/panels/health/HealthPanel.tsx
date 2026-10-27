import { StatusDot } from "@nova/ui";
import { Panel } from "@nova/ui";
import { useEffect, useState } from "react";

import { useModuleHealth, withStaleness } from "../../entities/health";

/**
 * Per-module health, as the modules themselves reported it.
 *
 * Purely push-fed: `nova-core` exposes only `/internal/*`, which is never
 * routable (doc 11 §3), so there is no endpoint to read and no polling to
 * do. The panel shows what the bus reported or shows that it has heard
 * nothing -- and those are different rows, not one merged "unknown".
 *
 * The interval below is **not** an animation clock. It re-evaluates
 * staleness, which is the case a decorative health board gets wrong: a
 * module that stopped reporting must fall back to `unknown` rather than
 * keep its last good status forever, and that transition is driven by time
 * passing rather than by an event arriving. No reducer can produce it.
 */

const STALENESS_TICK_MS = 5_000;

export function HealthPanel() {
  const { data } = useModuleHealth();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), STALENESS_TICK_MS);
    return () => clearInterval(timer);
  }, []);

  const modules = withStaleness(data ?? {}, now);

  return (
    <Panel
      title="Health"
      accessory={
        <span className="nova-status" data-testid="health-module-count">
          {modules.length} module{modules.length === 1 ? "" : "s"}
        </span>
      }
    >
      {modules.length === 0 ? (
        <p className="m-auto text-sm opacity-60" data-testid="panel-empty">
          No module has reported health yet.
        </p>
      ) : (
        <ul className="flex list-none flex-col gap-2 overflow-y-auto p-0" data-testid="health-list">
          {modules.map((module) => (
            <li key={module.module} className="nova-card" data-testid="health-module">
              <div className="flex items-center justify-between gap-3">
                <StatusDot
                  status={
                    module.status === "starting" ? "degraded" : module.status
                  }
                  instrument={`health:${module.module}`}
                  label={module.module}
                />
                <span className="nova-status" data-testid="health-source">
                  via {module.source}
                </span>
              </div>
              {module.reason ? (
                <p className="m-0 pt-1 text-sm opacity-80" data-testid="health-reason">
                  {module.reason}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
