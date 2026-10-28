import { mockGet, mockRun } from './mock';
import { getServerUrl, readCache, writeCache } from './storage';
import type { AlertItem, Field, FieldView, IrrigationEvent, Reading, Result, RunResult } from './types';

export const TIMEOUT_MS = 8000;
export const MOCK = process.env.EXPO_PUBLIC_MOCK === '1';

export const OFFLINE_MESSAGE = 'Cannot reach the server. Check the address in Settings.';

// ---- Errors --------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public kind: 'timeout' | 'network' | 'http' | 'parse',
    message: string,
    public status?: number,
  ) {
    super(message);
  }
}

/** Plain language for the farmer. */
export function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.kind === 'http') return `The server had a problem (error ${e.status}). Try again soon.`;
    if (e.kind === 'parse') return 'The server sent data this app could not read.';
  }
  return OFFLINE_MESSAGE;
}

// ---- Low level request ---------------------------------------------------

export function normalizeServerUrl(input: string): string {
  let url = input.trim();
  if (!url) return '';
  if (!/^https?:\/\//i.test(url)) url = `http://${url}`;
  return url.replace(/\/+$/, '');
}

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/** Fetch JSON with an 8 second limit for the whole request, including reading the body. */
async function request(path: string, init: RequestInit = {}, baseUrl?: string): Promise<unknown> {
  if (MOCK) {
    await wait(250);
    return init.method === 'POST' ? mockRun() : mockGet(path);
  }
  const base = baseUrl ?? (await getServerUrl());
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${base}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { Accept: 'application/json', ...(init.headers ?? {}) },
    });
    if (!res.ok) throw new ApiError('http', `HTTP ${res.status}`, res.status);
    try {
      return await res.json();
    } catch {
      if (controller.signal.aborted) throw new ApiError('timeout', 'Timed out');
      throw new ApiError('parse', 'Bad JSON');
    }
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (controller.signal.aborted) throw new ApiError('timeout', 'Timed out');
    throw new ApiError('network', 'Network request failed');
  } finally {
    clearTimeout(timer);
  }
}

// ---- Defensive parsing (never crash on a missing field) ------------------

const num = (v: unknown): number | null => {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v))) return Number(v);
  return null;
};
const str = (v: unknown): string | null => (typeof v === 'string' ? v : null);
const rows = (raw: unknown): Record<string, unknown>[] =>
  Array.isArray(raw) ? raw.filter((x): x is Record<string, unknown> => typeof x === 'object' && x !== null) : [];

function parseFields(raw: unknown): Field[] {
  return rows(raw).flatMap((r) => {
    const id = num(r.id);
    if (id === null) return [];
    return [{ id, name: str(r.name) ?? `Field ${id}`, node_id: str(r.node_id), crop: str(r.crop) }];
  });
}

function parseReadings(raw: unknown): Reading[] {
  return rows(raw).flatMap((r) => {
    const field_id = num(r.field_id);
    if (field_id === null) return [];
    return [
      {
        id: num(r.id) ?? 0,
        field_id,
        field_name: str(r.field_name),
        soil_moisture: num(r.soil_moisture),
        temperature: num(r.temperature),
        humidity: num(r.humidity),
        recorded_at: str(r.recorded_at),
        received_at: str(r.received_at),
        valid: num(r.valid) ?? 1,
        flag: str(r.flag),
      },
    ];
  });
}

function parseAlerts(raw: unknown): AlertItem[] {
  return rows(raw).flatMap((r) => {
    const id = num(r.id);
    if (id === null) return [];
    return [
      {
        id,
        field_id: num(r.field_id),
        kind: str(r.kind) ?? 'unknown',
        message: str(r.message) ?? 'Something needs your attention.',
        created_at: str(r.created_at),
        resolved: num(r.resolved) ?? 0,
      },
    ];
  });
}

function parseEvents(raw: unknown): IrrigationEvent[] {
  return rows(raw).flatMap((r) => {
    const id = num(r.id);
    if (id === null) return [];
    return [
      {
        id,
        field_id: num(r.field_id),
        field_name: str(r.field_name),
        action: str(r.action) ?? 'unknown',
        source: str(r.source) ?? 'unknown',
        duration_min: num(r.duration_min),
        created_at: str(r.created_at),
      },
    ];
  });
}

function parseRun(raw: unknown): RunResult[] {
  return rows(raw).flatMap((r) => {
    const field_id = num(r.field_id);
    if (field_id === null) return [];
    return [
      {
        field_id,
        field_name: str(r.field_name),
        action: str(r.action) ?? 'unknown',
        reason: str(r.reason) ?? 'unknown',
        duration_min: num(r.duration_min),
        moisture: num(r.moisture),
      },
    ];
  });
}

// ---- GET with cache fallback ---------------------------------------------

/**
 * Try the network. On success, save the result on the phone and return it.
 * On failure, return the last saved result marked stale. Throws only when there is nothing saved.
 */
async function loadWithCache<T>(name: string, path: string, parse: (raw: unknown) => T): Promise<Result<T>> {
  try {
    const data = parse(await request(path));
    if (!MOCK) await writeCache(name, data);
    return { data, stale: false, savedAt: null };
  } catch (e) {
    const cached = await readCache<T>(name);
    if (cached) return { data: cached.data, stale: true, savedAt: cached.savedAt };
    throw e;
  }
}

export const loadFields = () => loadWithCache('fields', '/fields', parseFields);
export const loadLatest = () => loadWithCache('latest', '/latest', parseReadings);
export const loadAlerts = () => loadWithCache('alerts', '/alerts', parseAlerts);
export const loadEvents = () => loadWithCache('events', '/schedule/events', parseEvents);

/** Last saved field list, without touching the network. Used to name fields in notifications. */
export async function getCachedFields(): Promise<Field[]> {
  return (await readCache<Field[]>('fields'))?.data ?? [];
}

// ---- Other calls ---------------------------------------------------------

/** Asks the backend to evaluate every field. Not cached. */
export async function runIrrigationCheck(): Promise<RunResult[]> {
  return parseRun(await request('/schedule/run', { method: 'POST' }));
}

/** Calls /health on the given server. Resolves when the server answers {"status":"ok"}. */
export async function checkHealth(baseUrl: string): Promise<'ok' | 'unexpected'> {
  const body = (await request('/health', {}, baseUrl)) as { status?: unknown } | null;
  return body && body.status === 'ok' ? 'ok' : 'unexpected';
}

// ---- Fields screen data --------------------------------------------------

/**
 * Fields joined with their newest reading. The readings call must succeed (fresh or saved),
 * because showing fields without readings would wrongly say "No data yet".
 * If only /fields fails, the field list is rebuilt from the readings.
 */
export async function loadFieldViews(): Promise<Result<FieldView[]>> {
  const [fieldsRes, latestRes] = await Promise.allSettled([loadFields(), loadLatest()]);
  if (latestRes.status === 'rejected') throw latestRes.reason;

  const latest = latestRes.value;
  const fields: Field[] =
    fieldsRes.status === 'fulfilled' && fieldsRes.value.data.length > 0
      ? fieldsRes.value.data
      : latest.data.map((r) => ({
          id: r.field_id,
          name: r.field_name ?? `Field ${r.field_id}`,
          node_id: null,
          crop: null,
        }));

  const newest = new Map<number, Reading>();
  for (const r of latest.data) {
    const current = newest.get(r.field_id);
    if (!current || r.id >= current.id) newest.set(r.field_id, r);
  }

  const views = [...fields]
    .sort((a, b) => a.id - b.id)
    .map((field) => ({ field, reading: newest.get(field.id) ?? null }));

  const parts = [latest, fieldsRes.status === 'fulfilled' ? fieldsRes.value : null];
  const stale = parts.some((p) => p?.stale);
  const times = parts.flatMap((p) => (p?.savedAt ? [p.savedAt] : []));
  return { data: views, stale, savedAt: times.length ? Math.min(...times) : null };
}
