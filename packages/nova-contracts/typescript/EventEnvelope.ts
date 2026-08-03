export type EventId = string;
/**
 * Dot-namespaced subject, e.g. 'memory.episodic.created'.
 */
export type Subject = string;
export type OccurredAt = string;
/**
 * The service/engine that published this event.
 */
export type SourceEngine = string;
/**
 * Ties an entire request lifecycle together end-to-end.
 */
export type CorrelationId = string;
/**
 * The event_id of the event that directly caused this one.
 */
export type CausationId = string | null;
export type Confidence = number | null;

/**
 * Common envelope wrapping every event published on the Event Bus.
 */
export interface EventEnvelope {
  event_id?: EventId;
  subject: Subject;
  occurred_at?: OccurredAt;
  source_engine: SourceEngine;
  correlation_id: CorrelationId;
  causation_id?: CausationId;
  confidence?: Confidence;
  payload?: Payload;
  [k: string]: unknown;
}
export interface Payload {
  [k: string]: unknown;
}
