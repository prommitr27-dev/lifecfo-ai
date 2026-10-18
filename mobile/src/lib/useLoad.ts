import { useCallback, useEffect, useState } from 'react';

import { useConnection } from './connection';

/** Load data for a screen; reloads when inputs change or any screen changes stored data. */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const { version } = useConnection();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(load, deps);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setData(await run());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [run]);

  useEffect(() => {
    refresh();
  }, [refresh, version]);

  return { data, error, loading, refresh };
}
