export type ObjectId = string;
export type Label = string;
export type UserId = string;
export type ObjectType = "project";
export type ProjectId = string | null;
export type SensorId = string;
export type ObservedAt = string;
export type SchemaVersion = number;

/**
 * Phase 4F.2, ratified in TDD 4F §20.2 -- the **object-shaped** perception
 * observation, produced from a `nova-companion` filesystem sensor.
 *
 * **Why a new subject was genuinely required (D-4D-1).**
 * `world-model-engine`'s `make_perception_observed_handler` needs
 * `object_id`, `label` and `user_id`. Every payload above is identity- or
 * sensor-shaped and carries none of the three -- there are zero occurrences
 * of `object_id`, `entity_id` or `object_label` in this module outside this
 * class. The subject is one segment, so it lands under that engine's
 * existing `perception.*.observed` wildcard and falls through
 * `make_perception_dispatch_handler`'s `else` branch **with zero world-model
 * changes**.
 *
 * **`object_id` is a file-path hash, never the path.** `WorldObject`'s own
 * docstring names *"a window handle, a file path hash, a project UUID"* as
 * the sanctioned handle forms. A raw filesystem path is user data that has
 * no business crossing the bus, and `perception-engine` hashes it before
 * this payload is ever constructed.
 *
 * **Internal only.** It carries raw sensor provenance -- `sensor_id`,
 * `observed_at`, a path hash -- so it is absent from `PUBLIC_TOPICS`,
 * `ws-gateway` cannot subscribe to it, and no browser can name it. The
 * browser sees *normalized* state through the Cognitive State REST surface
 * instead.
 */
export interface PerceptionWorkspaceObservedPayload {
  object_id: ObjectId;
  label: Label;
  user_id: UserId;
  object_type: ObjectType;
  project_id?: ProjectId;
  sensor_id: SensorId;
  observed_at: ObservedAt;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
