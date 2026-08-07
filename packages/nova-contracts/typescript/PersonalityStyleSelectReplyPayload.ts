/**
 * Bible Part 13's nine-style palette.
 */
export type CommunicationStyle =
  | "professional"
  | "educational"
  | "technical"
  | "friendly"
  | "executive"
  | "creative"
  | "minimal"
  | "analytical"
  | "emergency";
export type Verbosity = string;
export type TechnicalDepth = string;
export type SchemaVersion = number;

export interface PersonalityStyleSelectReplyPayload {
  style: CommunicationStyle;
  verbosity: Verbosity;
  technical_depth: TechnicalDepth;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
