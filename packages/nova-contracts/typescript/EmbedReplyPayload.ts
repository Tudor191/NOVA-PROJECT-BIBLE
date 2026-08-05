export type Embeddings = number[][];
export type ModelId = string;
export type Provider = string;
export type Error = string | null;
export type SchemaVersion = number;

export interface EmbedReplyPayload {
  embeddings: Embeddings;
  model_id: ModelId;
  provider: Provider;
  error?: Error;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
