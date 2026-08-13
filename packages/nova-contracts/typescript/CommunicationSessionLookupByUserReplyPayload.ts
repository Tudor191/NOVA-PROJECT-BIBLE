export type UserId = string;
export type SessionId = string | null;
export type SchemaVersion = number;

export interface CommunicationSessionLookupByUserReplyPayload {
  user_id: UserId;
  session_id?: SessionId;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
