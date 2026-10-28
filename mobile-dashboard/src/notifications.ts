import { Alert, Platform } from 'react-native';
import { getCachedFields, loadAlerts } from './api';
import { IN_EXPO_GO } from './env';
import { alertMeta } from './format';
import {
  getLastSeenAlertId,
  getNotificationsEnabled,
  getPermissionAsked,
  getServerUrl,
  setLastSeenAlertId,
  setPermissionAsked,
} from './storage';
import type { AlertItem, Result } from './types';

export const ALERT_CHANNEL_ID = 'alerts';
export const ALERT_POLL_MS = 30_000;

export type PermissionState = 'granted' | 'denied' | 'undetermined' | 'unavailable';

type NotificationsModule = typeof import('expo-notifications');
let loaded: NotificationsModule | null | undefined;

/**
 * Loads expo-notifications on first use. Returns null where it cannot run (Expo Go on Android),
 * so the rest of the app keeps working and notifications are simply off.
 */
function getNotifications(): NotificationsModule | null {
  if (loaded !== undefined) return loaded;
  if (IN_EXPO_GO && Platform.OS === 'android') {
    loaded = null;
    return null;
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require('expo-notifications') as NotificationsModule;
    // Show notifications even while the app is open.
    mod.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowBanner: true,
        shouldShowList: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
      }),
    });
    loaded = mod;
  } catch {
    loaded = null;
  }
  return loaded;
}

/** False in Expo Go on Android. Settings uses this to explain why notifications are off. */
export function notificationsAvailable(): boolean {
  return getNotifications() !== null;
}

// ---- Channel and permission ----------------------------------------------

/** Android needs the channel to exist before a notification can make a sound or pop up. */
export async function ensureAlertChannel(): Promise<void> {
  const N = getNotifications();
  if (!N || Platform.OS !== 'android') return;
  await N.setNotificationChannelAsync(ALERT_CHANNEL_ID, {
    name: 'Alerts',
    importance: N.AndroidImportance.HIGH,
    vibrationPattern: [0, 250, 250, 250],
    sound: 'default',
  });
}

export async function getPermissionState(): Promise<PermissionState> {
  const N = getNotifications();
  if (!N) return 'unavailable';
  try {
    const p = await N.getPermissionsAsync();
    if (p.granted) return 'granted';
    return p.status === N.PermissionStatus.UNDETERMINED ? 'undetermined' : 'denied';
  } catch {
    return 'denied';
  }
}

export async function requestPermission(): Promise<PermissionState> {
  const N = getNotifications();
  if (!N) return 'unavailable';
  try {
    await ensureAlertChannel();
    await N.requestPermissionsAsync();
  } catch {
    // fall through to the state check
  }
  return getPermissionState();
}

/** First launch only: one line of explanation, then the system prompt. A "No" is respected. */
export async function askPermissionOnFirstLaunch(): Promise<void> {
  if (!notificationsAvailable()) return;
  if (await getPermissionAsked()) return;
  await setPermissionAsked();
  if ((await getPermissionState()) !== 'undetermined') return;
  await new Promise<void>((resolve) => {
    Alert.alert(
      'Turn on alerts',
      'SafeAgri ZM sends a notification when one of your fields has a problem.',
      [
        { text: 'Not now', style: 'cancel', onPress: () => resolve() },
        {
          text: 'Allow',
          onPress: () => {
            requestPermission().finally(resolve);
          },
        },
      ],
      { cancelable: false },
    );
  });
}

// ---- Delivering one alert ------------------------------------------------

// ===========================================================================
// REMOTE PUSH PLUG-IN POINT (not built yet)
//
// Today alerts arrive by polling GET /alerts. To add real push later:
//   1. Get a token here, with Notifications.getExpoPushTokenAsync() (Expo Push)
//      or Notifications.getDevicePushTokenAsync() (FCM directly).
//   2. Send the token to the backend. That needs a new backend endpoint, which
//      does not exist, so it is out of scope for now.
//   3. When a push arrives, call deliverAlert(alert) below, or let the OS show it.
// deliverAlert is the single place that turns an alert into a notification, so
// polling and push can share it. checkAlerts() already ignores ids it has seen,
// so the two sources will not notify twice.
// ===========================================================================

async function fieldNameFor(fieldId: number | null): Promise<string | null> {
  if (fieldId === null) return null;
  const fields = await getCachedFields();
  return fields.find((f) => f.id === fieldId)?.name ?? `Field ${fieldId}`;
}

/** Shows one local notification right now, titled by kind, for example "Sensor fault, Field 2". */
export async function deliverAlert(alert: AlertItem): Promise<void> {
  const N = getNotifications();
  if (!N) return;
  const fieldName = await fieldNameFor(alert.field_id);
  const label = alertMeta(alert.kind).label;
  await N.scheduleNotificationAsync({
    identifier: `alert-${alert.id}`,
    content: {
      title: fieldName ? `${label}, ${fieldName}` : label,
      body: alert.message,
      sound: 'default',
      data: { alertId: alert.id },
    },
    trigger: Platform.OS === 'android' ? { channelId: ALERT_CHANNEL_ID } : null,
  });
}

// ---- The check shared by the foreground poller and the background task ---

/**
 * Notifies for every alert with an id higher than the highest one already seen.
 * The very first successful fetch only records what exists, so nothing is flooded.
 * Returns how many notifications were shown.
 */
export async function processNewAlerts(alerts: AlertItem[]): Promise<number> {
  const baseUrl = await getServerUrl();
  const maxId = alerts.reduce((m, a) => Math.max(m, a.id), 0);
  const lastSeen = await getLastSeenAlertId(baseUrl);

  if (lastSeen === null) {
    await setLastSeenAlertId(baseUrl, maxId);
    return 0;
  }

  const fresh = alerts.filter((a) => a.id > lastSeen).sort((a, b) => a.id - b.id);
  if (fresh.length === 0) return 0;

  // Record them first, so a second overlapping run cannot notify twice.
  await setLastSeenAlertId(baseUrl, Math.max(lastSeen, maxId));

  if (!(await getNotificationsEnabled())) return 0;
  if ((await getPermissionState()) !== 'granted') return 0;

  let shown = 0;
  for (const alert of fresh) {
    try {
      await deliverAlert(alert);
      shown += 1;
    } catch {
      // One bad notification must not stop the others.
    }
  }
  return shown;
}

let inFlight: Promise<Result<AlertItem[]>> | null = null;

/**
 * Fetch /alerts and notify for new ones. Used by the 30 second poller and by the
 * background task, so both run exactly the same check. Overlapping calls share one run.
 * Only fresh data counts: a cached answer never triggers a notification.
 */
export function checkAlerts(): Promise<Result<AlertItem[]>> {
  if (!inFlight) {
    inFlight = (async () => {
      try {
        const result = await loadAlerts();
        if (!result.stale) await processNewAlerts(result.data);
        return result;
      } finally {
        inFlight = null;
      }
    })();
  }
  return inFlight;
}
