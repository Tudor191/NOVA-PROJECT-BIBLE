export type Acknowledged = boolean;
export type SchemaVersion = number;

export interface ExecutiveOutcomeReportReplyPayload {
  acknowledged?: Acknowledged;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
