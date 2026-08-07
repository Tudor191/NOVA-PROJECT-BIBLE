export type UserId = string;
export type Preferences = {
  [k: string]: unknown;
} | null;
export type SchemaVersion = number;

export interface DigitalTwinPreferencesGetReplyPayload {
  user_id: UserId;
  preferences?: Preferences;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
