import { useState } from 'react';
import { Text, TextInput, View } from 'react-native';

import { Banner, Body, Button, Card, ErrorState, H2, Loading, Metric, Row, Screen } from '../../components/ui';
import type { OpResult } from '../../lib/api';
import { useConnection } from '../../lib/connection';
import { thb } from '../../lib/format';
import { useTheme } from '../../lib/theme';
import { useLoad } from '../../lib/useLoad';

function Field({
  label,
  value,
  onChange,
  numeric,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  numeric?: boolean;
}) {
  const t = useTheme();
  return (
    <View style={{ flex: 1, minWidth: 120, gap: 4 }}>
      <Text style={{ color: t.muted, fontSize: 12 }}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={(v) => onChange(numeric ? v.replace(/[^0-9]/g, '') : v)}
        keyboardType={numeric ? 'number-pad' : 'default'}
        maxLength={numeric ? 8 : 60}
        style={{
          minHeight: 44,
          borderWidth: 1,
          borderColor: t.border,
          borderRadius: 10,
          paddingHorizontal: 10,
          color: t.text,
          backgroundColor: t.card,
        }}
      />
    </View>
  );
}

export default function SandboxScreen() {
  const t = useTheme();
  const { client, changed } = useConnection();
  const { data, error, loading, refresh } = useLoad(() => client.sandbox(), [client]);
  const [outcome, setOutcome] = useState<OpResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [shockName, setShockName] = useState('Car repair');
  const [shockAmount, setShockAmount] = useState('10000');
  const [withdraw, setWithdraw] = useState('1000');
  const [days, setDays] = useState('30');

  // Every action here is a tap by the user in the app: that is what makes it a user decision.
  async function run(key: string, fn: () => Promise<OpResult>) {
    setBusy(key);
    try {
      setOutcome(await fn());
    } catch (e) {
      setOutcome({ ok: false, code: 'ERROR', message: (e as Error).message, data: {} });
    } finally {
      setBusy(null);
      changed();
    }
  }

  return (
    <Screen refreshing={loading && !!data} onRefresh={refresh}>
      {outcome ? (
        <Banner tone={outcome.ok ? 'good' : 'bad'} title={outcome.code}>
          {outcome.message}
        </Banner>
      ) : null}
      {error ? <ErrorState message={error} onRetry={refresh} /> : null}
      {!data && !error ? <Loading /> : null}
      {data ? (
        <>
          <Row>
            <Metric label="Sandbox date" value={data.as_of} />
            <Metric label="Sandbox cash" value={thb(data.total_cash_satang)} />
            <Metric label="Audit log" value={data.audit_intact ? 'Intact' : 'Altered'} hint="hash-chained" />
          </Row>
          <Body muted>A simulated account. No real money, bank, or credentials are involved.</Body>

          <H2>Waiting for your decision</H2>
          {data.pending.length === 0 ? (
            <Body muted>No proposals. Propose a plan from Personal CFO or ask in the chat.</Body>
          ) : null}
          {data.pending.map((p) => (
            <Card key={p.plan_id}>
              <Text style={{ color: t.text, fontWeight: '700', fontSize: 16 }}>{p.label} plan</Text>
              <Body muted>
                {p.plan_id} · proposed {p.created_at}
              </Body>
              <Row>
                <View style={{ flex: 1 }}>
                  <Button
                    label="Approve"
                    busy={busy === `a-${p.plan_id}`}
                    onPress={() => run(`a-${p.plan_id}`, () => client.decide(p.plan_id, true))}
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Button
                    kind="secondary"
                    label="Reject"
                    busy={busy === `r-${p.plan_id}`}
                    onPress={() => run(`r-${p.plan_id}`, () => client.decide(p.plan_id, false))}
                  />
                </View>
              </Row>
            </Card>
          ))}

          <H2>Approved, ready to execute</H2>
          {data.ready.length === 0 ? <Body muted>Nothing approved is waiting.</Body> : null}
          {data.ready.map((a) => (
            <Card key={a.approval_id}>
              <Text style={{ color: t.text, fontWeight: '700', fontSize: 16 }}>{a.label} plan</Text>
              <Body muted>approval {a.approval_id}</Body>
              <Button
                label="Execute in sandbox"
                busy={busy === a.approval_id}
                onPress={() => run(a.approval_id, () => client.execute(a.approval_id))}
              />
            </Card>
          ))}

          <H2>Record something that really happened</H2>
          <Card>
            <Body muted>
              Only for real events, not what-ifs. A confirmed expense becomes an essential bill, so
              earlier proposals must be redone.
            </Body>
            <Row>
              <Field label="What was it?" value={shockName} onChange={setShockName} />
              <Field label="Amount (THB)" value={shockAmount} onChange={setShockAmount} numeric />
            </Row>
            <Button
              kind="danger"
              label="Confirm this expense"
              disabled={!shockName.trim() || !Number(shockAmount)}
              busy={busy === 'expense'}
              onPress={() => run('expense', () => client.confirmExpense(shockName.trim(), Number(shockAmount)))}
            />
          </Card>

          {data.emergency_balance_satang > 0 ? (
            <Card>
              <Body>Emergency reserve: {thb(data.emergency_balance_satang)}</Body>
              <Field label="Withdraw (THB)" value={withdraw} onChange={setWithdraw} numeric />
              <Button
                kind="secondary"
                label="Withdraw from reserve"
                disabled={!Number(withdraw)}
                busy={busy === 'withdraw'}
                onPress={() => run('withdraw', () => client.withdrawReserve(Number(withdraw)))}
              />
            </Card>
          ) : null}

          <H2>Move time forward</H2>
          <Card>
            <Field label="Days" value={days} onChange={setDays} numeric />
            <Button
              kind="secondary"
              label="Post scheduled transactions"
              disabled={!Number(days) || Number(days) > 366}
              busy={busy === 'advance'}
              onPress={() => run('advance', () => client.advance(Number(days)))}
            />
            <Body muted>Refused if cash would run short.</Body>
          </Card>

          <H2>Sandbox transactions</H2>
          <Card>
            {data.transactions.length === 0 ? <Body muted>No transactions yet.</Body> : null}
            {data.transactions.slice(-15).reverse().map((r) => (
              <Row key={r.id} style={{ justifyContent: 'space-between' }}>
                <Body muted>
                  {r.on} · {r.kind}
                </Body>
                <Body>{thb(r.amount_satang)}</Body>
              </Row>
            ))}
          </Card>

          <H2>Audit log</H2>
          <Card>
            {data.audit.slice().reverse().slice(0, 20).map((e) => (
              <View key={e.seq} style={{ borderTopWidth: 1, borderTopColor: t.border, paddingTop: 6 }}>
                <Text style={{ color: t.text, fontWeight: '600' }}>
                  #{e.seq} {e.action}
                  {e.code ? ` · ${e.code}` : ''}
                </Text>
                <Body muted>
                  {e.actor} · {e.ts} · {e.hash}
                </Body>
              </View>
            ))}
          </Card>

          <Button kind="danger" label="Reset sandbox" busy={busy === 'reset'} onPress={() => run('reset', () => client.reset())} />
        </>
      ) : null}
    </Screen>
  );
}
