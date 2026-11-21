export type ImageBytes = string;
export type ImageFormat = "jpeg" | "png";
/**
 * Bible Part 7's privacy classification, propagated on every entity per
 * docs/design/phase-1/00-shared-foundations.md's "Confidence and privacy,
 * everywhere" convention. Enforcement point is the Model Orchestration Engine
 * (Phase 2); Phase 1 stores and propagates the field correctly from day one.
 */
export type PrivacyLevel = "public" | "internal" | "confidential" | "highly_sensitive";
export type RequestingEngine = string;
export type CorrelationId = string;
export type SchemaVersion = number;

/**
 * Event Bus RPC for faceprint extraction (docs/design/phase-2d/
 * 03-perception-engine.md §0.2) -- `perception-engine`'s only legal path to a
 * face-embedding model, per ADR-020. `image_bytes` carries one already-detected
 * face crop, never a full frame -- face detection itself is this connector's
 * own concern (mirrors `TranscribeRequestPayload`'s "caller decides utterance
 * boundaries" boundary, applied here to face-region boundaries instead).
 */
export interface FaceEmbedRequestPayload {
  image_bytes: ImageBytes;
  image_format?: ImageFormat;
  privacy_hint?: PrivacyLevel;
  requesting_engine: RequestingEngine;
  correlation_id: CorrelationId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
