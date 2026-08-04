export type RunId = string;
export type RecordsScanned = number;
export type RecordsMerged = number;
export type RecordsAdvanced = number;
export type RecordsDeleted = number;
export type Status = string;

export interface ConsolidationCompletedPayload {
  run_id: RunId;
  records_scanned: RecordsScanned;
  records_merged: RecordsMerged;
  records_advanced: RecordsAdvanced;
  records_deleted: RecordsDeleted;
  status: Status;
  [k: string]: unknown;
}
