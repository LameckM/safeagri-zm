// Defines the background task. Must be imported at startup, before the OS wakes the app.
import '../src/background';

import { Slot } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect } from 'react';
import { registerAlertTask } from '../src/background';
import { AlertsProvider } from '../src/AlertsProvider';
import { askPermissionOnFirstLaunch, ensureAlertChannel } from '../src/notifications';
import { getNotificationsEnabled } from '../src/storage';

export default function RootLayout() {
  useEffect(() => {
    (async () => {
      await ensureAlertChannel();
      await askPermissionOnFirstLaunch();
      if (await getNotificationsEnabled()) await registerAlertTask();
    })().catch(() => {
      // Never let setup problems stop the app from opening.
    });
  }, []);

  return (
    <AlertsProvider>
      <StatusBar style="dark" />
      <Slot />
    </AlertsProvider>
  );
}
