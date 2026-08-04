export type MemoryId = string;
export type EmbeddingModel = string;
export type Dimensions = number;

export interface EmbeddingCompletedPayload {
  memory_id: MemoryId;
  embedding_model: EmbeddingModel;
  dimensions: Dimensions;
  [k: string]: unknown;
}
