import { Text, View } from 'react-native';

import { useConnection } from '../lib/connection';
import { useTheme } from '../lib/theme';
import { Chips } from './ui';

const OPTIONS = [0, -10, -30, -50, -100, 10] as const;

/** Hypothetical income change. Simulated on a copy by the server; nothing is saved. */
export function WhatIf() {
  const t = useTheme();
  const { incomeChange, setIncomeChange } = useConnection();
  return (
    <View style={{ gap: 6 }}>
      <Text style={{ color: t.muted, fontSize: 13 }}>What-if: income change (nothing is saved)</Text>
      <Chips
        options={OPTIONS}
        value={incomeChange as (typeof OPTIONS)[number]}
        onChange={setIncomeChange}
        format={(v) => (v === 0 ? 'Actual' : `${v > 0 ? '+' : ''}${v}%`)}
      />
    </View>
  );
}
