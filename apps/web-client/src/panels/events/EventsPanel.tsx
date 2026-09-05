import { ConfidenceBadge, CorrelationTag, Panel } from "@nova/ui";

import { EVENT_FEED_LIMIT, useEventFeed } from "../../entities/events";

/**
 * Every frame that reached this browser.
 *
 * No data source of its own -- it renders the socket. That makes it the
 * first place to look when another panel is empty: an empty transcript with
 * `communication.turn.received` visible here is a rendering fault, and an
 * empty transcript with nothing here is a transport one.
 *
 * Both timestamps are shown, and labelled, because they answer different
 * questions. `generated_at` is when the engine said it happened;
 * `receivedAt` is this browser's clock when the frame arrived. Showing one
 * as the other is how out-of-order delivery becomes invisible.
 */
export function EventsPanel() {
  const { data } = useEventFeed();
  const events = data ?? [];

  return (
    <Panel
      title="Events"
      accessory={
        <span className="nova-status" data-testid="event-count">
          {events.length === EVENT_FEED_LIMIT
            ? `last ${EVENT_FEED_LIMIT}`
            : `${events.length} received`}
        </span>
      }
    >
      {events.length === 0 ? (
        <p className="m-auto text-sm opacity-60" data-testid="panel-empty">
          No events received on this connection yet.
        </p>
      ) : (
        <ol className="flex list-none flex-col gap-2 overflow-y-auto p-0" data-testid="event-list">
          {events.map((event) => (
            <li key={event.seq} className="nova-card" data-testid="event">
              <div className="flex flex-wrap items-center gap-2">
                <span className="nova-badge" data-testid="event-topic">
                  {event.topic}
                </span>
                <ConfidenceBadge confidence={event.confidence} />
                <CorrelationTag correlationId={event.correlationId} />
              </div>
              <p className="m-0 pt-1 text-sm opacity-70" data-testid="event-times">
                occurred {new Date(event.generatedAt).toLocaleTimeString()} · received{" "}
                {new Date(event.receivedAt).toLocaleTimeString()}
              </p>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}
