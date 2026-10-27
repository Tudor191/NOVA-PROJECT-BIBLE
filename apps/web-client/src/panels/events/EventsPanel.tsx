import { Button, ConfidenceBadge, CorrelationTag, Panel, TextField } from "@nova/ui";

import { EVENT_FEED_LIMIT, filterEvents, useEventFeed } from "../../entities/events";
import { useUiStore } from "../../shared/store";

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
  const filters = useUiStore((state) => state.eventFilters);
  const setEventFilter = useUiStore((state) => state.setEventFilter);
  const clearEventFilters = useUiStore((state) => state.clearEventFilters);

  const events = data ?? [];
  // Filtered for display only. `events` stays whole, so the count below can
  // say how much is being hidden rather than pretending it never arrived,
  // and so clearing a filter brings everything straight back.
  const visible = filterEvents(events, filters);
  const filtering = events.length !== visible.length || Boolean(filters.topic || filters.correlationId);

  return (
    <Panel
      title="Events"
      accessory={
        <span className="nova-status" data-testid="event-count">
          {filtering
            ? `${visible.length} of ${events.length} shown`
            : events.length === EVENT_FEED_LIMIT
              ? `last ${EVENT_FEED_LIMIT}`
              : `${events.length} received`}
        </span>
      }
    >
      <div className="flex flex-wrap items-end gap-3 pb-3" data-testid="event-filters">
        <TextField
          label="Topic"
          data-testid="event-filter-topic"
          value={filters.topic}
          placeholder="e.g. action.approval"
          onChange={(event) => setEventFilter("topic", event.target.value)}
        />
        <TextField
          label="Correlation id"
          data-testid="event-filter-correlation"
          value={filters.correlationId}
          placeholder="e.g. 4f1d9c2a"
          onChange={(event) => setEventFilter("correlationId", event.target.value)}
        />
        <Button variant="ghost" data-testid="event-filter-clear" onClick={clearEventFilters}>
          Clear
        </Button>
      </div>

      {visible.length === 0 ? (
        // Two different facts, and conflating them is what this panel exists
        // to prevent: nothing has arrived at all, versus nothing matches what
        // is currently being asked for.
        filtering ? (
          <p className="m-auto text-sm opacity-60" data-testid="panel-no-matches">
            No events match this filter. {events.length} received on this connection.
          </p>
        ) : (
          <p className="m-auto text-sm opacity-60" data-testid="panel-empty">
            No events received on this connection yet.
          </p>
        )
      ) : (
        <ol className="flex list-none flex-col gap-2 overflow-y-auto p-0" data-testid="event-list">
          {visible.map((event) => (
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
