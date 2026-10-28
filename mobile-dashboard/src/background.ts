import { IN_EXPO_GO } from './env';
import { checkAlerts } from './notifications';

/**
 * Best effort background check. The operating system decides when (if ever) this runs,
 * usually 15 minutes or more apart, and iOS is stricter. See the README.
 *
 * This file must be imported once at startup (app/_layout.tsx) so the task is defined
 * before the OS wakes the app. In Expo Go the task is not used at all.
 */
export const ALERT_TASK = 'safeagri-alert-check';

type FetchModule = typeof import('expo-background-fetch');
type TaskModule = typeof import('expo-task-manager');

function load(): { BackgroundFetch: FetchModule; TaskManager: TaskModule } | null {
  if (IN_EXPO_GO) return null;
  try {
    return {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      BackgroundFetch: require('expo-background-fetch') as FetchModule,
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      TaskManager: require('expo-task-manager') as TaskModule,
    };
  } catch {
    return null;
  }
}

const modules = load();

if (modules) {
  const { BackgroundFetch, TaskManager } = modules;
  try {
    TaskManager.defineTask(ALERT_TASK, async () => {
      try {
        await checkAlerts();
        return BackgroundFetch.BackgroundFetchResult.NewData;
      } catch {
        return BackgroundFetch.BackgroundFetchResult.Failed;
      }
    });
  } catch {
    // Background alerts are best effort. Never stop the app from opening.
  }
}

export async function registerAlertTask(): Promise<boolean> {
  if (!modules) return false;
  const { BackgroundFetch, TaskManager } = modules;
  try {
    const status = await BackgroundFetch.getStatusAsync();
    if (
      status === BackgroundFetch.BackgroundFetchStatus.Restricted ||
      status === BackgroundFetch.BackgroundFetchStatus.Denied
    ) {
      return false;
    }
    if (await TaskManager.isTaskRegisteredAsync(ALERT_TASK)) return true;
    await BackgroundFetch.registerTaskAsync(ALERT_TASK, {
      minimumInterval: 15 * 60,
      stopOnTerminate: false,
      startOnBoot: true,
    });
    return true;
  } catch {
    return false;
  }
}

export async function unregisterAlertTask(): Promise<void> {
  if (!modules) return;
  const { BackgroundFetch, TaskManager } = modules;
  try {
    if (await TaskManager.isTaskRegisteredAsync(ALERT_TASK)) {
      await BackgroundFetch.unregisterTaskAsync(ALERT_TASK);
    }
  } catch {
    // ignore
  }
}
