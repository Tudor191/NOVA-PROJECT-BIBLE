import { Button, DegradationNotice, Panel } from "@nova/ui";
import { useState } from "react";

import { GatewayError } from "../../entities/envelope";
import {
  type CapabilityManifest,
  useCapabilities,
  useInstallCapability,
  useUninstallCapability,
} from "../../entities/capabilities";
import { AsyncPanelBody } from "../shared/AsyncPanelBody";

/**
 * What NOVA can currently do, and the two controls that change it.
 *
 * The only panel with no live half. `capability-engine` publishes no domain
 * events, so there is nothing to subscribe to -- and the header says
 * "as of this read" rather than letting the absence of updates look like
 * stability. That is also why both mutations invalidate the list: with no
 * push channel, a re-read is the only way the panel learns what it just
 * changed, and it is not polling because it happens once, on an operator
 * action, rather than on a timer.
 *
 * **The manifest is entered as JSON, deliberately.** `POST /v1/capabilities/install`
 * takes `CapabilityManifest`, two of whose ten fields are themselves JSON
 * Schema documents (`input_schema`, `output_schema`). A field-by-field form
 * would have to invent a UI grammar for those two, and would then be a
 * second, weaker validator sitting in front of the engine's real one. The
 * engine validates the manifest; this panel's job is to submit it and show
 * what the engine said.
 */
export function CapabilitiesPanel() {
  const { data, isPending, error, dataUpdatedAt } = useCapabilities();
  const install = useInstallCapability();
  const uninstall = useUninstallCapability();
  const [manifestText, setManifestText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);

  const capabilities = data?.data ?? [];

  function submitManifest() {
    let manifest: CapabilityManifest;
    try {
      manifest = JSON.parse(manifestText) as CapabilityManifest;
    } catch {
      // Caught here rather than sent: a malformed body would come back as an
      // opaque 422 from the engine, and "that is not JSON" is something this
      // side already knows.
      setParseError("That is not valid JSON.");
      return;
    }
    setParseError(null);
    install.mutate(manifest, { onSuccess: () => setManifestText("") });
  }

  const installError = install.error;

  return (
    <Panel
      title="Capabilities"
      accessory={
        <span className="nova-status" data-testid="capabilities-read-at">
          {dataUpdatedAt ? `as of ${new Date(dataUpdatedAt).toLocaleTimeString()}` : "not read yet"}
        </span>
      }
    >
      <div className="flex min-h-0 flex-col gap-3">
        <section className="flex flex-col gap-2" data-testid="capability-install">
          <label className="text-sm opacity-80" htmlFor="capability-manifest">
            Install a capability — paste its manifest
          </label>
          <textarea
            id="capability-manifest"
            className="nova-card min-h-24 font-mono text-xs"
            data-testid="capability-manifest-input"
            value={manifestText}
            spellCheck={false}
            onChange={(event) => setManifestText(event.target.value)}
            placeholder='{"name": "...", "version": "1.0.0", "execution_adapter": "filesystem", ...}'
          />
          <div className="flex items-center gap-3">
            <Button
              busy={install.isPending}
              disabled={manifestText.trim().length === 0}
              onClick={submitManifest}
            >
              Install
            </Button>
            {parseError ? (
              <span className="nova-status" data-testid="capability-manifest-error">
                {parseError}
              </span>
            ) : null}
          </div>
          {/*
            The engine's own refusal, not a rendering of one. A manifest that
            fails dependency resolution or the sandbox probe comes back 422
            naming the stage, and that message is the useful part.
          */}
          {installError ? (
            <div data-testid="capability-install-error">
              <DegradationNotice
                title="This capability was not installed"
                detail={installError instanceof Error ? installError.message : String(installError)}
                code={installError instanceof GatewayError ? installError.code : null}
                correlationId={
                  installError instanceof GatewayError ? installError.correlationId : null
                }
              />
            </div>
          ) : null}
        </section>

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
                  <span className="flex items-center gap-3">
                    <span className="nova-status">
                      {capability.category} · v{capability.version}
                    </span>
                    <Button
                      variant="ghost"
                      busy={uninstall.isPending && uninstall.variables === capability.id}
                      data-testid="capability-uninstall"
                      onClick={() => uninstall.mutate(capability.id)}
                    >
                      Uninstall
                    </Button>
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
      </div>
    </Panel>
  );
}
