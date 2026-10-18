// Server address, token, and the what-if setting, shared by every screen.

import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { type Client, type Connection, createClient } from './api';

const STORAGE_KEY = 'lifecfo.connection.v1';

/**
 * Default server address. In development the phone already talks to the Expo
 * dev server on the laptop, so the API is assumed to run on the same machine,
 * port 8000. EXPO_PUBLIC_API_URL overrides this (for a deployed API).
 */
function defaultBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  if (fromEnv) return fromEnv;
  const hostUri = Constants.expoConfig?.hostUri; // e.g. "192.168.1.20:8081"
  const host = hostUri?.split(':')[0];
  if (host) return `http://${host}:8000`;
  if (typeof window !== 'undefined' && window.location?.hostname) {
    return `http://${window.location.hostname}:8000`;
  }
  return 'http://localhost:8000';
}

type Ctx = {
  connection: Connection;
  setConnection: (c: Connection) => Promise<void>;
  client: Client;
  incomeChange: number;
  setIncomeChange: (v: number) => void;
  // Bumped after any change to stored data so every screen reloads.
  version: number;
  changed: () => void;
};

const ConnectionContext = createContext<Ctx | null>(null);

export function ConnectionProvider({ children }: { children: ReactNode }) {
  const [connection, setConn] = useState<Connection>({
    baseUrl: defaultBaseUrl(),
    token: process.env.EXPO_PUBLIC_API_TOKEN ?? '',
  });
  const [incomeChange, setIncomeChange] = useState(0);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((raw) => {
        if (raw) {
          setConn(JSON.parse(raw) as Connection);
          setVersion((v) => v + 1);
        }
      })
      .catch(() => undefined);
  }, []);

  const setConnection = useCallback(async (c: Connection) => {
    setConn(c);
    setVersion((v) => v + 1);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(c)).catch(() => undefined);
  }, []);

  const changed = useCallback(() => setVersion((v) => v + 1), []);
  const client = useMemo(() => createClient(connection), [connection]);

  const value = useMemo(
    () => ({ connection, setConnection, client, incomeChange, setIncomeChange, version, changed }),
    [connection, setConnection, client, incomeChange, version, changed],
  );
  return <ConnectionContext.Provider value={value}>{children}</ConnectionContext.Provider>;
}

export function useConnection(): Ctx {
  const ctx = useContext(ConnectionContext);
  if (!ctx) throw new Error('useConnection must be used inside ConnectionProvider');
  return ctx;
}
