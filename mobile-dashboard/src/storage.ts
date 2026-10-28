import AsyncStorage from '@react-native-async-storage/async-storage';

/** Everything the app keeps on the phone. Every call is wrapped so storage errors never crash the app. */

export const DEFAULT_SERVER_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://192.168.1.50:8000';

const KEYS = {
  serverUrl: 'safeagri:serverUrl',
  dismissed: 'safeagri:dismissedAlertIds',
  lastSeen: 'safeagri:lastSeenAlert',
  notifications: 'safeagri:notificationsEnabled',
  permissionAsked: 'safeagri:permissionAsked',
  cache: (name: string) => `safeagri:cache:${name}`,
};

async function getItem(key: string): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(key);
  } catch {
    return null;
  }
}

async function setItem(key: string, value: string): Promise<void> {
  try {
    await AsyncStorage.setItem(key, value);
  } catch {
    // Storage full or unavailable. The app still works without it.
  }
}

async function removeItem(key: string): Promise<void> {
  try {
    await AsyncStorage.removeItem(key);
  } catch {
    // ignore
  }
}

// ---- Server URL ----------------------------------------------------------

let memoryUrl: string | null = null;

export async function getServerUrl(): Promise<string> {
  if (memoryUrl) return memoryUrl;
  const url = (await getItem(KEYS.serverUrl)) ?? DEFAULT_SERVER_URL;
  memoryUrl = url;
  return url;
}

export async function setServerUrl(url: string): Promise<void> {
  const previous = await getServerUrl();
  memoryUrl = url;
  await setItem(KEYS.serverUrl, url);
  // Alert ids belong to one server, so dismissed ids do not carry over to another.
  if (previous !== url) await removeItem(KEYS.dismissed);
}

// ---- Response cache ------------------------------------------------------

export type CacheEntry<T> = { baseUrl: string; savedAt: number; data: T };

export async function writeCache<T>(name: string, data: T): Promise<void> {
  const entry: CacheEntry<T> = { baseUrl: await getServerUrl(), savedAt: Date.now(), data };
  await setItem(KEYS.cache(name), JSON.stringify(entry));
}

/** Returns the cached response, or null when none exists or it came from a different server. */
export async function readCache<T>(name: string): Promise<CacheEntry<T> | null> {
  const raw = await getItem(KEYS.cache(name));
  if (!raw) return null;
  try {
    const entry = JSON.parse(raw) as CacheEntry<T>;
    if (!entry || entry.baseUrl !== (await getServerUrl())) return null;
    if (typeof entry.savedAt !== 'number') return null;
    return entry;
  } catch {
    return null;
  }
}

// ---- Dismissed alerts (this phone only) ----------------------------------

export async function getDismissedIds(): Promise<number[]> {
  const raw = await getItem(KEYS.dismissed);
  if (!raw) return [];
  try {
    const list = JSON.parse(raw);
    return Array.isArray(list) ? list.filter((n): n is number => typeof n === 'number') : [];
  } catch {
    return [];
  }
}

export async function setDismissedIds(ids: number[]): Promise<void> {
  await setItem(KEYS.dismissed, JSON.stringify(ids));
}

// ---- Highest alert id already seen ---------------------------------------

/** null means this phone has never recorded alerts from this server. */
export async function getLastSeenAlertId(baseUrl: string): Promise<number | null> {
  const raw = await getItem(KEYS.lastSeen);
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as { baseUrl?: string; id?: number };
    if (v.baseUrl !== baseUrl || typeof v.id !== 'number') return null;
    return v.id;
  } catch {
    return null;
  }
}

export async function setLastSeenAlertId(baseUrl: string, id: number): Promise<void> {
  await setItem(KEYS.lastSeen, JSON.stringify({ baseUrl, id }));
}

// ---- Notification settings -----------------------------------------------

export async function getNotificationsEnabled(): Promise<boolean> {
  return (await getItem(KEYS.notifications)) !== 'off';
}

export async function setNotificationsEnabled(enabled: boolean): Promise<void> {
  await setItem(KEYS.notifications, enabled ? 'on' : 'off');
}

export async function getPermissionAsked(): Promise<boolean> {
  return (await getItem(KEYS.permissionAsked)) === 'yes';
}

export async function setPermissionAsked(): Promise<void> {
  await setItem(KEYS.permissionAsked, 'yes');
}
