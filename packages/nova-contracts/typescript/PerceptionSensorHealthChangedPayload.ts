export type SensorId = string;
export type SensorType = string;
export type Status = string;
export type SchemaVersion = number;

/**
 * `sensor_type`/`status` remain plain `str` here, matching
 * `nova_perception_engine`'s own domain layer, which does not constrain
 * either to a fixed vocabulary today -- this is a registration of the
 * existing shape, not a new constraint (module docstring).
 */
export interface PerceptionSensorHealthChangedPayload {
  sensor_id: SensorId;
  sensor_type: SensorType;
  status: Status;
  schema_version?: SchemaVersion;
  [k: string]: unknown;
}
