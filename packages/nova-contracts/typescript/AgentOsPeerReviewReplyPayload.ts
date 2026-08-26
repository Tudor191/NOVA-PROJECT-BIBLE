export type PeerValidation = "approved" | "rejected" | "timed_out" | "not_required";
export type SchemaVersion = number;

export interface AgentOsPeerReviewReplyPayload {
  peer_validation: PeerValidation;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
