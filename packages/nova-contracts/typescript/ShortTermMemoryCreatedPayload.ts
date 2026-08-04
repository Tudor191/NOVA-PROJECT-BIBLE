export type ShortTermId = string;
export type UserId = string;
export type ProjectId = string | null;
export type Category = string;
export type ExpiresAt = string;

export interface ShortTermMemoryCreatedPayload {
  short_term_id: ShortTermId;
  user_id: UserId;
  project_id?: ProjectId;
  category: Category;
  expires_at: ExpiresAt;
  [k: string]: unknown;
}
