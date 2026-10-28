export type Field = {
  id: number;
  name: string;
  node_id: string | null;
  crop: string | null;
};

export type Reading = {
  id: number;
  field_id: number;
  field_name: string | null;
  soil_moisture: number | null;
  temperature: number | null;
  humidity: number | null;
  recorded_at: string | null;
  received_at: string | null;
  valid: number;
  flag: string | null;
};

export type AlertItem = {
  id: number;
  field_id: number | null;
  kind: string;
  message: string;
  created_at: string | null;
  resolved: number;
};

export type IrrigationEvent = {
  id: number;
  field_id: number | null;
  field_name: string | null;
  action: string;
  source: string;
  duration_min: number | null;
  created_at: string | null;
};

export type RunResult = {
  field_id: number;
  field_name: string | null;
  action: string;
  reason: string;
  duration_min: number | null;
  moisture: number | null;
};

/** What a loader returns. stale is true when the data came from the phone cache. */
export type Result<T> = {
  data: T;
  stale: boolean;
  /** Epoch ms when the data was saved on this phone. Only set when stale. */
  savedAt: number | null;
};

/** A field joined with its newest reading, ready for the Fields screen. */
export type FieldView = {
  field: Field;
  reading: Reading | null;
};
