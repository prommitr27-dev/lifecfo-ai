import { useState } from 'react';
import { Switch, Text, View } from 'react-native';

import { Banner, Body, Button, Card, ErrorState, H2, Loading, Metric, Progress, Row, Screen } from '../../components/ui';
import type { Rewards } from '../../lib/api';
import { useConnection } from '../../lib/connection';
import { thb } from '../../lib/format';
import { useTheme } from '../../lib/theme';
import { useLoad } from '../../lib/useLoad';

const STREAK_STATE: Record<string, string> = {
  NOT_STARTED: 'Not started',
  ACTIVE: 'Active',
  PROTECTED: 'Protected',
  PAUSED: 'Paused',
  BROKEN: 'Start again any time',
};

export default function RewardsScreen() {
  const t = useTheme();
  const { client } = useConnection();
  const { data: loaded, error, loading, refresh } = useLoad(() => client.rewards(), [client]);
  const [override, setOverride] = useState<Rewards | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const data = override ?? loaded;

  async function act(fn: () => Promise<{ status: Rewards; note?: string } | Rewards>) {
    setBusy(true);
    try {
      const result = await fn();
      if ('status' in result && typeof result.status === 'object') {
        setOverride(result.status);
        setMessage(result.note ?? null);
      } else {
        setOverride(result as Rewards);
        setMessage(null);
      }
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const onRefresh = () => {
    setOverride(null);
    refresh();
  };

  return (
    <Screen refreshing={loading && !!data} onRefresh={onRefresh}>
      {error ? <ErrorState message={error} onRetry={onRefresh} /> : null}
      {!data && !error ? <Loading /> : null}
      {data ? (
        <>
          <Card>
            <Row style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={{ color: t.text, fontSize: 16, fontWeight: '600' }}>Use rewards and streaks</Text>
              <Switch
                value={data.opted_in}
                disabled={busy}
                onValueChange={(v) => act(() => client.setOptIn(v))}
              />
            </Row>
            <Body muted>Switching off stops all recording. Goal progress stays visible.</Body>
          </Card>
          {message ? <Banner tone="good">{message}</Banner> : null}

          <H2>Goal progress</H2>
          <Card>
            {data.goal_progress.map((g) => (
              <View key={g.goal} style={{ gap: 4 }}>
                <Body>
                  {g.goal}: {thb(g.saved)} of {thb(g.target)} ({g.percent}%)
                </Body>
                <Progress value={g.percent / 100} />
              </View>
            ))}
          </Card>

          {data.opted_in && data.streaks ? (
            <>
              <H2>Your CFO companion</H2>
              <Card>
                <Text style={{ color: t.text, fontSize: 20, fontWeight: '800' }}>Level {data.level}</Text>
                {data.next_level_at_xp ? (
                  <>
                    <Progress value={(data.xp ?? 0) / data.next_level_at_xp} />
                    <Body muted>
                      {data.xp} of {data.next_level_at_xp} XP to the next level
                    </Body>
                  </>
                ) : (
                  <Body muted>{data.xp} XP, top level</Body>
                )}
              </Card>
              <Row>
                {(['DAILY', 'WEEKLY'] as const).map((k) => {
                  const s = data.streaks![k];
                  const state = s.status === 'PROTECTED' && s.protected_until
                    ? `Protected until ${s.protected_until}`
                    : STREAK_STATE[s.status];
                  return (
                    <Metric
                      key={k}
                      label={k === 'DAILY' ? 'Daily streak' : 'Weekly streak'}
                      value={String(s.count)}
                      hint={`${state} · best ${s.best}`}
                    />
                  );
                })}
              </Row>

              <H2>This week&apos;s missions</H2>
              <Card>
                {data.missions?.note ? <Banner tone="info">{data.missions.note}</Banner> : null}
                {data.missions?.items.map((m) => (
                  <Body key={m.id}>
                    {m.done ? '✅' : '⬜️'} {m.title}
                  </Body>
                ))}
              </Card>
              <Button
                label="I reviewed my bills and plan today"
                busy={busy}
                onPress={() =>
                  act(async () => {
                    const r = await client.recordReview();
                    return {
                      status: r.status,
                      note: r.recorded ? 'Check-in recorded.' : 'Already recorded for today.',
                    };
                  })
                }
              />
              {Object.values(data.streaks).some((s) => s.status === 'PAUSED') ? (
                <Button kind="secondary" label="Resume streaks" onPress={() => act(() => client.resumeStreaks())} />
              ) : (
                <Button kind="secondary" label="Pause streaks" onPress={() => act(() => client.pauseStreaks())} />
              )}

              {data.badges?.length ? (
                <>
                  <H2>Badges</H2>
                  <Row>
                    {data.badges.map((b) => (
                      <View key={b} style={{ backgroundColor: t.infoBg, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6 }}>
                        <Text style={{ color: t.info, fontWeight: '600' }}>🏅 {b}</Text>
                      </View>
                    ))}
                  </Row>
                </>
              ) : null}
            </>
          ) : null}
          <Body muted>{data.note}</Body>
        </>
      ) : null}
    </Screen>
  );
}
