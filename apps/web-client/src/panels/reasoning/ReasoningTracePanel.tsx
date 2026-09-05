import { ConfidenceTierBadge, CorrelationTag, Panel } from "@nova/ui";

import { useLiveProcesses, useReasoningTraces } from "../../entities/reasoning";
import { AsyncPanelBody } from "../shared/AsyncPanelBody";

/**
 * How NOVA reached its conclusions.
 *
 * Two lists, kept separate on purpose. The recorded traces are what
 * reasoning-engine persisted; the live processes are what finished while
 * this panel was open. Merging them would imply the live ones are already
 * durable, and a process that completed on the bus is not the same fact as
 * a trace written to a database.
 *
 * Confidence is rendered as a **tier word, never a number** -- the tier is
 * reasoning-engine's own vocabulary, and a percentage would invent a
 * precision the engine never claimed. A failed process shows no badge at
 * all rather than a zero.
 */

function tierOf(score: number | null): string {
  // The same four-tier vocabulary `confidence_tier_label` uses server-side.
  // Duplicated deliberately rather than imported: it is not on the wire for
  // traces, and the alternative is rendering a raw float.
  if (score === null) return "unknown";
  if (score >= 0.85) return "high";
  if (score >= 0.6) return "moderate";
  if (score >= 0.3) return "low";
  return "very_low";
}

export function ReasoningTracePanel() {
  const { data, isPending, error } = useReasoningTraces();
  const { data: live } = useLiveProcesses();
  const traces = data?.data ?? [];
  const liveProcesses = live ?? [];

  return (
    <Panel
      title="Reasoning Trace"
      accessory={
        <span className="nova-status" data-testid="live-process-count">
          {liveProcesses.length} live
        </span>
      }
    >
      <AsyncPanelBody
        isPending={isPending}
        error={error}
        isEmpty={traces.length === 0 && liveProcesses.length === 0}
        emptyLabel="No reasoning recorded yet."
      >
        <div className="flex flex-col gap-4 overflow-y-auto">
          {liveProcesses.length > 0 ? (
            <section data-testid="live-processes">
              <h3 className="m-0 pb-2 text-sm opacity-70">Completed while watching</h3>
              <ul className="m-0 flex list-none flex-col gap-2 p-0">
                {liveProcesses.map((process) => (
                  <li key={process.reasoningProcessId} className="nova-card" data-testid="live-process">
                    <div className="flex items-center gap-2">
                      <span className="nova-badge" data-testid="live-process-outcome">
                        {process.outcome}
                      </span>
                      {process.outcome === "completed" ? (
                        <ConfidenceTierBadge tier={tierOf(process.confidence)} />
                      ) : null}
                      <CorrelationTag correlationId={process.correlationId} />
                    </div>
                    {process.error ? (
                      <p className="m-0 pt-1 text-sm opacity-80" data-testid="live-process-error">
                        {process.error}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section data-testid="recorded-traces">
            <h3 className="m-0 pb-2 text-sm opacity-70">Recorded traces</h3>
            <ul className="m-0 flex list-none flex-col gap-2 p-0" data-testid="trace-list">
              {traces.map((trace) => (
                <li key={trace.id} className="nova-card" data-testid="trace">
                  <div className="flex items-center gap-2">
                    <span className="nova-badge" data-testid="trace-mode">
                      {trace.reasoning_mode}
                    </span>
                    <span className="nova-status">level {trace.reasoning_level}</span>
                    <ConfidenceTierBadge tier={tierOf(trace.confidence_score)} />
                    <CorrelationTag correlationId={trace.correlation_id} />
                  </div>
                  {trace.selected_capabilities.length > 0 ? (
                    <p className="m-0 pt-1 text-sm opacity-80" data-testid="trace-capabilities">
                      used: {trace.selected_capabilities.join(", ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        </div>
      </AsyncPanelBody>
    </Panel>
  );
}
