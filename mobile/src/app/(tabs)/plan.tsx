import { router } from 'expo-router';
import { useState } from 'react';
import { Text, View } from 'react-native';

import { WhatIf } from '../../components/WhatIf';
import {
  Banner,
  Body,
  Button,
  Card,
  Chips,
  ErrorState,
  H2,
  Loading,
  MarkdownText,
  Row,
  Screen,
} from '../../components/ui';
import type { OpResult, PlanSummary } from '../../lib/api';
import { useConnection } from '../../lib/connection';
import { thb } from '../../lib/format';
import { useTheme } from '../../lib/theme';
import { useLoad } from '../../lib/useLoad';

const HORIZONS = [6, 12, 18, 24] as const;

function PlanCard({ plan, selected, onSelect }: { plan: PlanSummary; selected: boolean; onSelect: () => void }) {
  const t = useTheme();
  const first = plan.first_month;
  return (
    <Card style={selected ? { borderColor: t.accent, borderWidth: 2 } : undefined}>
      <Text onPress={onSelect} style={{ color: t.text, fontSize: 17, fontWeight: '700' }}>
        {plan.label}
      </Text>
      <Body muted>
        Reserve reached:{' '}
        {plan.reserve ? (plan.reserve.reached_month ?? 'not in horizon') : 'no reserve'}
      </Body>
      {plan.goals.map((g) => (
        <Body key={g.id}>
          {g.name}: {g.completion_month ?? 'not in horizon'}
          {g.on_track === false ? ` (late, ${thb(g.shortfall_at_deadline_satang)} short)` : ''}
        </Body>
      ))}
      <Body muted>
        Flexible spending in {first.month}: {thb(first.flexible_total_satang)} of{' '}
        {thb(first.flexible_max_satang)}
      </Body>
      {Object.entries(first.contributions_satang).length ? (
        <Body muted>
          Saved in {first.month}:{' '}
          {Object.entries(first.contributions_satang)
            .map(([k, v]) => `${k} ${thb(v)}`)
            .join(', ')}
        </Body>
      ) : null}
      <Row>
        <Body muted>Months below buffer: {plan.months_below_buffer.length}</Body>
        <Body muted>· Goals at risk: {plan.goals_at_risk.length}</Body>
      </Row>
      {!selected ? <Button kind="secondary" label="Select" onPress={onSelect} /> : null}
    </Card>
  );
}

export default function PlanScreen() {
  const { client, incomeChange, changed } = useConnection();
  const [horizon, setHorizon] = useState<(typeof HORIZONS)[number]>(12);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<OpResult | null>(null);
  const { data, error, loading, refresh } = useLoad(
    () => client.plans(horizon, incomeChange),
    [client, horizon, incomeChange],
  );

  const plan = data?.plans.find((p) => p.strategy === selected) ?? data?.plans[0];

  async function requestApproval() {
    if (!plan) return;
    setBusy(true);
    try {
      setOutcome(await client.propose(plan.strategy, horizon));
      changed();
    } catch (e) {
      setOutcome({ ok: false, code: 'ERROR', message: String((e as Error).message), data: {} });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen refreshing={loading && !!data} onRefresh={refresh}>
      <WhatIf />
      <Chips options={HORIZONS} value={horizon} onChange={setHorizon} format={(m) => `${m} months`} />
      {error ? <ErrorState message={error} onRetry={refresh} /> : null}
      {!data && !error ? <Loading /> : null}
      {data ? (
        <>
          {data.position_text ? (
            <Card>
              <MarkdownText text={data.position_text} />
            </Card>
          ) : null}

          {data.status === 'ESSENTIAL_SHORTFALL' ? (
            <Banner tone="bad" title="No plan can pay essentials">
              From {data.essential_shortfall_on} the shortfall reaches{' '}
              {thb(data.essential_shortfall_satang)} even with no flexible spending, no savings, and
              the whole reserve used. Nothing is reduced to make a plan fit.
            </Banner>
          ) : data.status === 'REQUIRES_RESERVE_DRAWDOWN' ? (
            <Banner tone="warn" title="Reserve drawdown needed">
              Essentials can only be paid by withdrawing from the emergency reserve. That is a
              recovery decision, so no regular plan is offered.
            </Banner>
          ) : data.status === 'FLEXIBLE_SPENDING_CONSTRAINT' ? (
            <Banner tone="warn" title="Preferences need a change">
              Even at your flexible minimum the budget runs short. A plan needs a change to one of
              your preferences, which is your decision.
            </Banner>
          ) : (
            <Banner tone="good" title={`${data.plans.length} plans`}>
              Each passed the deterministic validator and the daily cash check.
            </Banner>
          )}
          {data.identical_notes.map((n, i) => (
            <Banner key={i} tone="info">
              {n}
            </Banner>
          ))}

          {data.plans.length ? <H2>Compare strategies</H2> : null}
          {data.plans.map((p) => (
            <PlanCard
              key={p.strategy}
              plan={p}
              selected={p.strategy === plan?.strategy}
              onSelect={() => setSelected(p.strategy)}
            />
          ))}

          {plan ? (
            <View style={{ gap: 8 }}>
              {data.hypothetical ? (
                <Banner tone="info">
                  This is a what-if view. Set income back to Actual to propose a plan.
                </Banner>
              ) : (
                <Button
                  label={`Request approval for ${plan.label}`}
                  onPress={requestApproval}
                  busy={busy}
                />
              )}
              {outcome ? (
                <Banner tone={outcome.ok ? 'good' : 'bad'} title={outcome.code}>
                  {outcome.message}
                </Banner>
              ) : null}
              {outcome?.ok ? (
                <Button kind="secondary" label="Open Sandbox to decide" onPress={() => router.navigate('/sandbox')} />
              ) : null}
              <Body muted>A plan is only a proposal until you approve it in the Sandbox.</Body>
            </View>
          ) : null}
        </>
      ) : null}
    </Screen>
  );
}
