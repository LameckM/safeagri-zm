import type { Reading } from './types';

/** Pure status rules. Same as the web dashboard. No React, no network. */

export const DRY_AT_OR_BELOW = 25;
export const WET_AT_OR_ABOVE = 60;
export const OFFLINE_AFTER_MS = 15 * 60 * 1000;

export type StatusKey = 'needs_water' | 'wet' | 'healthy' | 'offline' | 'no_data';
export type StatusTone = 'red' | 'blue' | 'green' | 'grey';
export type StatusIcon =
  | 'alert-circle'
  | 'water'
  | 'checkmark-circle'
  | 'cloud-offline'
  | 'help-circle';

export type StatusInfo = {
  key: StatusKey;
  label: string;
  tone: StatusTone;
  icon: StatusIcon;
};

export const STATUS: Record<StatusKey, StatusInfo> = {
  needs_water: { key: 'needs_water', label: 'Needs water', tone: 'red', icon: 'alert-circle' },
  wet: { key: 'wet', label: 'Wet', tone: 'blue', icon: 'water' },
  healthy: { key: 'healthy', label: 'Healthy', tone: 'green', icon: 'checkmark-circle' },
  offline: { key: 'offline', label: 'Node offline', tone: 'red', icon: 'cloud-offline' },
  no_data: { key: 'no_data', label: 'No data yet', tone: 'grey', icon: 'help-circle' },
};

/** Parse an ISO timestamp to epoch ms. Returns null when missing or invalid. */
export function parseTime(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : null;
}

/** Moisture only, ignoring freshness. */
export function classifyMoisture(moisture: number): StatusInfo {
  if (moisture <= DRY_AT_OR_BELOW) return STATUS.needs_water;
  if (moisture >= WET_AT_OR_ABOVE) return STATUS.wet;
  return STATUS.healthy;
}

type ReadingLike = Pick<Reading, 'soil_moisture' | 'recorded_at' | 'received_at'>;

/**
 * Status of one field.
 * 1. No reading at all, or no moisture value: No data yet.
 * 2. Reading older than 15 minutes (or with no usable time): Node offline.
 * 3. Otherwise by moisture: at or below 25 Needs water, at or above 60 Wet, else Healthy.
 */
export function getFieldStatus(reading: ReadingLike | null | undefined, now: number): StatusInfo {
  if (!reading || reading.soil_moisture === null || !Number.isFinite(reading.soil_moisture)) {
    return STATUS.no_data;
  }
  const t = parseTime(reading.recorded_at) ?? parseTime(reading.received_at);
  if (t === null) return STATUS.offline;
  if (now - t > OFFLINE_AFTER_MS) return STATUS.offline;
  return classifyMoisture(reading.soil_moisture);
}
