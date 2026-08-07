export type MemoryId = string;
export type UserId = string;
export type UpdatedFields = string[];
export type Version = number;
export type SchemaVersion = number;

export interface LongTermMemoryUpdatedPayload {
  memory_id: MemoryId;
  user_id: UserId;
  updated_fields: UpdatedFields;
  version: Version;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
