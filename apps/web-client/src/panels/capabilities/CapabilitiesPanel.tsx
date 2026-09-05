import { Panel } from "@nova/ui";

import { useCapabilities } from "../../entities/capabilities";
import { AsyncPanelBody } from "../shared/AsyncPanelBody";

/**
 * What NOVA can currently do.
 *
 * The only panel with no live half. `capability-engine` publishes no domain
 * events, so there is nothing to subscribe to -- and the header says
 * "as of this read" rather than letting the absence of updates look like
 * stability.
 */
export function CapabilitiesPanel() {
  const { data, isPending, error, dataUpdatedAt } = useCapabilities();
  const capabilities = data?.data ?? [];

  return (
    <Panel
      title="Capabilities"
      accessory={
        <span className="nova-status" data-testid="capabilities-read-at">
          {dataUpdatedAt ? `as of ${new Date(dataUpdatedAt).toLocaleTimeString()}` : "not read yet"}
        </span>
      }
    >
      <AsyncPanelBody
        isPending={isPending}
        error={error}
        isEmpty={capabilities.length === 0}
        emptyLabel="No capabilities installed."
      >
        <ul
          className="flex list-none flex-col gap-3 overflow-y-auto p-0"
          data-testid="capability-list"
        >
          {capabilities.map((capability) => (
            <li key={capability.id} className="nova-card" data-testid="capability">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-medium">{capability.name}</span>
                <span className="nova-status">
                  {capability.category} · v{capability.version}
                </span>
              </div>
              <p className="m-0 pt-1 text-sm opacity-80">{capability.description}</p>
              {capability.required_permissions.length > 0 ? (
                <p className="m-0 pt-1 text-sm opacity-70" data-testid="capability-permissions">
                  requires: {capability.required_permissions.join(", ")}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      </AsyncPanelBody>
    </Panel>
  );
}
