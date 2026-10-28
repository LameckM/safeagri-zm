import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { AppState } from 'react-native';
import { describeError } from './api';
import { ALERT_POLL_MS, checkAlerts } from './notifications';
import { getDismissedIds, setDismissedIds } from './storage';
import type { AlertItem } from './types';

type AlertsContextValue = {
  /** Active alerts that have not been dismissed on this phone. */
  alerts: AlertItem[];
  count: number;
  stale: boolean;
  savedAt: number | null;
  error: string | null;
  loaded: boolean;
  refresh: () => Promise<void>;
  dismiss: (id: number) => void;
};

const AlertsContext = createContext<AlertsContextValue | null>(null);

export function useAlerts(): AlertsContextValue {
  const ctx = useContext(AlertsContext);
  if (!ctx) throw new Error('useAlerts must be used inside AlertsProvider');
  return ctx;
}

/**
 * Owns the foreground poll. Every 30 seconds while the app is open it calls checkAlerts(),
 * which fetches /alerts and shows a local notification for any new alert.
 * The Alerts screen and the tab badge both read from here, so there is one request, not three.
 */
export function AlertsProvider({ children }: { children: React.ReactNode }) {
  const [all, setAll] = useState<AlertItem[]>([]);
  const [dismissed, setDismissed] = useState<number[]>([]);
  const [stale, setStale] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const hasData = useRef(false);
  const dismissedRef = useRef<number[]>([]);

  const refresh = useCallback(async () => {
    const stored = await getDismissedIds();
    dismissedRef.current = stored;
    setDismissed(stored);
    try {
      const result = await checkAlerts();
      hasData.current = true;
      setAll(result.data);
      setStale(result.stale);
      setSavedAt(result.savedAt);
      setError(null);
      if (!result.stale) {
        // Forget dismissed ids that are no longer active, so the list does not grow forever.
        const active = new Set(result.data.map((a) => a.id));
        const kept = stored.filter((id) => active.has(id));
        if (kept.length !== stored.length) {
          dismissedRef.current = kept;
          setDismissed(kept);
          await setDismissedIds(kept);
        }
      }
    } catch (e) {
      if (hasData.current) {
        // Keep showing what we have, and say it is old.
        setStale(true);
      } else {
        setError(describeError(e));
      }
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    const stop = () => {
      if (timer) clearInterval(timer);
      timer = null;
    };
    const start = () => {
      stop();
      refresh();
      timer = setInterval(refresh, ALERT_POLL_MS);
    };
    if (AppState.currentState === 'active') start();
    // No polling while the app is in the background. That saves battery and data.
    const sub = AppState.addEventListener('change', (state) => (state === 'active' ? start() : stop()));
    return () => {
      stop();
      sub.remove();
    };
  }, [refresh]);

  const dismiss = useCallback((id: number) => {
    const next = Array.from(new Set([...dismissedRef.current, id]));
    dismissedRef.current = next;
    setDismissed(next);
    setDismissedIds(next);
  }, []);

  const value = useMemo<AlertsContextValue>(() => {
    const visible = all.filter((a) => !dismissed.includes(a.id));
    return { alerts: visible, count: visible.length, stale, savedAt, error, loaded, refresh, dismiss };
  }, [all, dismissed, stale, savedAt, error, loaded, refresh, dismiss]);

  return <AlertsContext.Provider value={value}>{children}</AlertsContext.Provider>;
}
