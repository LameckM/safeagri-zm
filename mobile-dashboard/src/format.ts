import { parseTime } from './status';
import type { RunResult } from './types';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const pad2 = (n: number) => String(n).padStart(2, '0');

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

/** "just now", "3 minutes ago", "2 hours ago", "4 days ago". */
export function timeAgo(iso: string | null | undefined, now: number): string {
  const t = parseTime(iso);
  if (t === null) return 'at an unknown time';
  const diff = Math.max(0, now - t);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${plural(minutes, 'minute')} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${plural(hours, 'hour')} ago`;
  return `${plural(Math.floor(hours / 24), 'day')} ago`;
}

/** "10:42" in the phone's local time. */
export function formatClock(epochMs: number): string {
  const d = new Date(epochMs);
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** "13 Oct, 09:20" in the phone's local time. */
export function formatDateTime(iso: string | null | undefined): string {
  const t = parseTime(iso);
  if (t === null) return 'Unknown time';
  const d = new Date(t);
  return `${d.getDate()} ${MONTHS[d.getMonth()]}, ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** One decimal for readings, "N/A" when the value is missing. */
export function formatValue(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'N/A';
  return `${value.toFixed(1)}${unit}`;
}

export type AlertMeta = { label: string; icon: 'warning' | 'cloud-offline' | 'alert-circle'; tone: 'amber' | 'red' };

/** Known kinds get their own label. Anything else gets a generic one. */
export function alertMeta(kind: string): AlertMeta {
  switch (kind) {
    case 'sensor_fault':
      return { label: 'Sensor fault', icon: 'warning', tone: 'amber' };
    case 'node_offline':
      return { label: 'Node offline', icon: 'cloud-offline', tone: 'red' };
    default:
      return { label: 'Alert', icon: 'alert-circle', tone: 'amber' };
  }
}

function capitalise(s: string): string {
  const spaced = s.replace(/_/g, ' ').trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : '';
}

/** "Opened for 30 minutes". */
export function describeEvent(action: string, durationMin: number | null): string {
  const hasDuration = durationMin !== null && Number.isFinite(durationMin);
  if (action === 'open') {
    return hasDuration ? `Opened for ${plural(durationMin as number, 'minute')}` : 'Opened';
  }
  if (action === 'close') return 'Closed';
  return capitalise(action) || 'Irrigation event';
}

/** "rule" becomes "Automatic rule". Unknown sources are shown as written. */
export function sourceLabel(source: string): string {
  if (source === 'rule') return 'Automatic rule';
  if (source === 'manual') return 'Manual';
  return capitalise(source) || 'Unknown source';
}

/** Short, readable message for the result of POST /schedule/run. */
export function summarizeRun(results: RunResult[]): string {
  if (results.length === 0) return 'The server checked, but there are no fields to irrigate.';
  const irrigating = results.filter((r) => r.action === 'irrigate');
  const offline = results.filter((r) => r.reason === 'node_offline');
  const parts: string[] = [];
  if (irrigating.length > 0) {
    const names = irrigating
      .map((r) => {
        const name = r.field_name ?? `Field ${r.field_id}`;
        return r.duration_min ? `${name} for ${plural(r.duration_min, 'minute')}` : name;
      })
      .join(', ');
    parts.push(`Irrigating: ${names}.`);
  } else {
    parts.push('No irrigation needed right now.');
  }
  if (offline.length > 0) {
    const names = offline.map((r) => r.field_name ?? `Field ${r.field_id}`).join(', ');
    parts.push(`Node offline: ${names}.`);
  }
  return parts.join(' ');
}
