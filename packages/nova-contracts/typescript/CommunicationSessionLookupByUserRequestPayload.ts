export type UserId = string;
export type SchemaVersion = number;

/**
 * Fork D's own "small, new capability": does this user have a
 * currently-connected session, and if so, which one. Scoped to exactly
 * one connected session per user, per `SessionRegistry`'s own
 * single-concurrent-session-per-instance assumption (ADR-025) -- not a
 * general multi-session index.
 */
export interface CommunicationSessionLookupByUserRequestPayload {
  user_id: UserId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
