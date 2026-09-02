import { z } from "zod";

/**
 * The wire format `ws-gateway` speaks, mirrored on the client.
 *
 * `PUBLIC_TOPICS` below must equal the gateway's own set exactly. That is
 * not a convention -- `tests/unit/topics.test.ts` reads
 * `services/ws-gateway/src/nova_ws_gateway/domain/protocol.py` and fails on
 * any difference. A client-side list that drifted would either ask for a
 * topic the gateway rejects (a visible error) or, worse, silently stop
 * asking for one it needs.
 *
 * Frames reuse doc 11 §4's `{data, meta, error}` envelope, so this client's
 * data layer sees one convention across REST and WebSocket rather than two.
 */

export const PUBLIC_TOPICS = [
  "communication.turn.received",
  "communication.intent.delivered",
  "communication.session.created",
  "communication.session.state_changed",
  "communication.session.completed",
  "perception.identity.observed",
  "perception.presence.observed",
  "nova.heartbeat",
] as const;

export type PublicTopic = (typeof PUBLIC_TOPICS)[number];

const frameMetaSchema = z.object({
  correlation_id: z.string(),
  generated_at: z.string(),
  confidence: z.number().nullable().optional(),
});

export const eventFrameSchema = z.object({
  type: z.literal("event"),
  topic: z.string(),
  data: z.record(z.string(), z.unknown()),
  meta: frameMetaSchema,
  error: z.null().optional(),
});

export const controlFrameSchema = z.object({
  type: z.enum(["ready", "subscribed", "unsubscribed", "error"]),
  topics: z.array(z.string()).default([]),
  error: z.object({ code: z.string(), message: z.string() }).nullable().optional(),
});

export const frameSchema = z.union([eventFrameSchema, controlFrameSchema]);

export type EventFrame = z.infer<typeof eventFrameSchema>;
export type ControlFrame = z.infer<typeof controlFrameSchema>;
export type Frame = EventFrame | ControlFrame;

export function isEventFrame(frame: Frame): frame is EventFrame {
  return frame.type === "event";
}

/** A frame that could not be parsed. Surfaced, never silently dropped. */
export class MalformedFrameError extends Error {}

export function parseFrame(raw: string): Frame {
  let json: unknown;
  try {
    json = JSON.parse(raw);
  } catch {
    throw new MalformedFrameError("The gateway sent a frame that is not JSON.");
  }
  const parsed = frameSchema.safeParse(json);
  if (!parsed.success) {
    throw new MalformedFrameError(
      `The gateway sent a frame that does not match the protocol: ${parsed.error.issues
        .map((i) => i.message)
        .join("; ")}`,
    );
  }
  return parsed.data;
}

export function subscribeMessage(topics: readonly string[]): string {
  return JSON.stringify({ action: "subscribe", topics });
}
