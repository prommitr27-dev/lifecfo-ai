import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { ConnectionProvider } from '../lib/connection';
import { useTheme } from '../lib/theme';

function Root() {
  const t = useTheme();
  return (
    <>
      <StatusBar style="auto" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: t.card },
          headerTintColor: t.text,
          contentStyle: { backgroundColor: t.bg },
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="settings" options={{ title: 'Server settings', presentation: 'modal' }} />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <ConnectionProvider>
      <Root />
    </ConnectionProvider>
  );
}
