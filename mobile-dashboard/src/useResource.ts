import { useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';
import { describeError } from './api';
import type { Result } from './types';

/**
 * Loads data when a tab is opened, and again on pull to refresh.
 * Loaders return cached data (stale: true) when the network fails, so error is only set
 * when there is nothing at all to show.
 */
export function useResource<T>(loader: () => Promise<Result<T>>, initial: T) {
  const [data, setData] = useState<T>(initial);
  const [stale, setStale] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [pulling, setPulling] = useState(false);

  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const initialRef = useRef(initial);

  const load = useCallback(async (fromPull = false) => {
    if (fromPull) setPulling(true);
    try {
      const result = await loaderRef.current();
      setData(result.data);
      setStale(result.stale);
      setSavedAt(result.savedAt);
      setError(null);
    } catch (e) {
      setData(initialRef.current);
      setStale(false);
      setError(describeError(e));
    } finally {
      setLoaded(true);
      setPulling(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  return { data, stale, savedAt, error, loaded, pulling, reload: () => load(false), pull: () => load(true) };
}
