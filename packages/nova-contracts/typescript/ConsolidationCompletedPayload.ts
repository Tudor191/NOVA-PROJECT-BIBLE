export type RunId = string;
export type RecordsScanned = number;
export type RecordsMerged = number;
export type RecordsAdvanced = number;
export type RecordsDeleted = number;
export type Status = string;
export type SchemaVersion = number;

export interface ConsolidationCompletedPayload {
  run_id: RunId;
  records_scanned: RecordsScanned;
  records_merged: RecordsMerged;
  records_advanced: RecordsAdvanced;
  records_deleted: RecordsDeleted;
  status: Status;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
