import { router } from 'expo-router';
import { useState } from 'react';
import { Text, TextInput, View } from 'react-native';

import { Banner, Body, Button, Card, Screen } from '../components/ui';
import { createClient } from '../lib/api';
import { useConnection } from '../lib/connection';
import { useTheme } from '../lib/theme';

export default function SettingsScreen() {
  const t = useTheme();
  const { connection, setConnection } = useConnection();
  const [baseUrl, setBaseUrl] = useState(connection.baseUrl);
  const [token, setToken] = useState(connection.token);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function test() {
    setBusy(true);
    try {
      const c = createClient({ baseUrl, token });
      const h = await c.health();
      await c.summary();
      setResult({ ok: true, text: `Connected.${h.auth_required ? ' Token accepted.' : ''}` });
    } catch (e) {
      setResult({ ok: false, text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  const input = {
    minHeight: 44,
    borderWidth: 1,
    borderColor: t.border,
    borderRadius: 10,
    paddingHorizontal: 10,
    color: t.text,
    backgroundColor: t.card,
  } as const;

  return (
    <Screen>
      <Card>
        <View style={{ gap: 4 }}>
          <Text style={{ color: t.muted, fontSize: 12 }}>Server address</Text>
          <TextInput
            value={baseUrl}
            onChangeText={setBaseUrl}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
            placeholder="http://192.168.1.20:8000"
            placeholderTextColor={t.muted}
            style={input}
          />
        </View>
        <View style={{ gap: 4 }}>
          <Text style={{ color: t.muted, fontSize: 12 }}>API token (only if the server sets one)</Text>
          <TextInput
            value={token}
            onChangeText={setToken}
            autoCapitalize="none"
            autoCorrect={false}
            secureTextEntry
            style={input}
          />
        </View>
        <Button kind="secondary" label="Test connection" onPress={test} busy={busy} />
        <Button
          label="Save"
          onPress={async () => {
            await setConnection({ baseUrl: baseUrl.trim(), token: token.trim() });
            router.back();
          }}
        />
      </Card>
      {result ? <Banner tone={result.ok ? 'good' : 'bad'}>{result.text}</Banner> : null}
      <Body muted>
        Run the API on your computer with `uv run uvicorn lifecfo.api.main:app --host 0.0.0.0 --port
        8000`. The phone must be on the same Wi-Fi. Use the computer&apos;s local IP address, not
        localhost.
      </Body>
    </Screen>
  );
}
