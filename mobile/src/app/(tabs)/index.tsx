import { useState } from 'react';
import { Text, View } from 'react-native';

import { WhatIf } from '../../components/WhatIf';
import {
  BalanceChart,
  Banner,
  Body,
  Card,
  Chips,
  ErrorState,
  H2,
  Loading,
  Metric,
  Row,
  Screen,
} from '../../components/ui';
import { useConnection } from '../../lib/connection';
import { thb } from '../../lib/format';
import { useTheme } from '../../lib/theme';
import { useLoad } from '../../lib/useLoad';

const HORIZONS = [30, 60, 92, 183] as const;

export default function CashFlowScreen() {
  const t = useTheme();
  const { client, incomeChange } = useConnection();
  const [horizon, setHorizon] = useState<(typeof HORIZONS)[number]>(92);
  const [width, setWidth] = useState(0);
  const { data, error, loading, refresh } = useLoad(
    () => client.cashflow(horizon, incomeChange),
    [client, horizon, incomeChange],
  );

  return (
    <Screen refreshing={loading && !!data} onRefresh={refresh}>
      <WhatIf />
      <Chips options={HORIZONS} value={horizon} onChange={setHorizon} format={(d) => `${d} days`} />
      {error ? <ErrorState message={error} onRetry={refresh} /> : null}
      {!data && !error ? <Loading /> : null}
      {data ? (
        <>
          {data.hypothetical ? (
            <Banner tone="info">What-if view: income {incomeChange}%. Nothing is saved.</Banner>
          ) : null}
          {data.status === 'FEASIBLE' ? (
            <Banner tone="good" title="Funded">
              The current plan is funded on every day of the next {horizon} days.
            </Banner>
          ) : data.status === 'PLAN_INFEASIBLE' ? (
            <Banner tone="warn" title="Plan runs short">
              Unallocated cash first goes negative on {data.first_shortfall_on} and the plan runs{' '}
              {thb(data.max_shortfall_satang)} short. Essentials can still be paid, so replanning
              can fix it.{data.needs_reserves ? ' Existing reserves would be needed.' : ''}
            </Banner>
          ) : (
            <Banner tone="bad" title="Essentials at risk">
              From {data.essential_shortfall_on}, essentials cannot be paid even with flexible
              spending cut and every envelope used. Shortfall: {thb(data.essential_shortfall_satang)}.
            </Banner>
          )}

          <Row>
            <Metric label="Cash today" value={thb(data.total_cash_satang)} />
            <Metric
              label="Lowest unallocated"
              value={thb(data.min_unallocated_satang)}
              hint={data.min_unallocated_on ?? undefined}
            />
            <Metric label="Envelopes at end" value={thb(data.closing_envelopes_satang)} />
          </Row>

          <Card>
            <H2>Projected daily balances</H2>
            <View onLayout={(e) => setWidth(e.nativeEvent.layout.width)}>
              <BalanceChart
                width={width}
                series={[
                  { label: 'Unallocated', values: data.days.map((d) => d.unallocated_satang), color: t.chartA },
                  { label: 'Total cash', values: data.days.map((d) => d.total_cash_satang), color: t.chartB },
                ]}
              />
            </View>
          </Card>

          <Card>
            <H2>Monthly summary</H2>
            {data.months.map((m) => (
              <View
                key={m.month}
                style={{ borderTopWidth: 1, borderTopColor: t.border, paddingTop: 8, gap: 2 }}
              >
                <Text style={{ color: t.text, fontWeight: '700' }}>{m.month}</Text>
                <Body muted>
                  Income {thb(m.income)} · Essentials {thb(m.essential)} · Flexible {thb(m.flexible)}
                  {m.debt_minimum ? ` · Debt ${thb(m.debt_minimum)}` : ''} · Saved {thb(m.transfers)}
                </Body>
                <Body>Closing cash {thb(m.closing_total_cash)}</Body>
              </View>
            ))}
          </Card>

          <Card>
            <H2>Upcoming cash events</H2>
            {data.events.slice(0, 12).map((e, i) => (
              <Row key={i} style={{ justifyContent: 'space-between' }}>
                <Body muted>
                  {e.on} · {e.name}
                </Body>
                <Body>{thb(e.amount_satang)}</Body>
              </Row>
            ))}
          </Card>
        </>
      ) : null}
    </Screen>
  );
}
